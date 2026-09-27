package net.pototskiy.bhsxray.vpn

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import android.os.Parcel
import android.os.ParcelFileDescriptor
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import net.pototskiy.bhsxray.pigeon.VpnStatus

/** Reads the service itself and observes :native death. No last-known VPN state. */
class VpnStatusConnection(
    private val context: Context,
    private val notify: (VpnStatus) -> Unit,
) {
    companion object {
        const val ACTION_BIND = "net.pototskiy.bhsxray.VPN_STATUS_BIND"
        const val DESCRIPTOR = "net.pototskiy.bhsxray.VpnStatus"
        const val READ_STATUS = IBinder.FIRST_CALL_TRANSACTION
        const val PROTECT_SOCKET = IBinder.FIRST_CALL_TRANSACTION + 1
    }

    private var binding: ServiceConnection? = null
    private var service: CompletableDeferred<IBinder>? = null
    @Volatile private var connectedBinder: IBinder? = null
    private var pending: CompletableDeferred<Unit>? = null
    private var target: VpnStatus? = null
    private var eventGeneration = 0

    suspend fun read(): VpnStatus = withContext(Dispatchers.Main) {
        target?.let {
            return@withContext if (it == VpnStatus.CONNECTED) VpnStatus.CONNECTING else VpnStatus.DISCONNECTING
        }
        if (service == null && !VpnController.readVpnRunning(context)) {
            return@withContext VpnStatus.DISCONNECTED
        }
        val binder = bind()
        withContext(Dispatchers.IO) {
            val request = Parcel.obtain()
            val reply = Parcel.obtain()
            try {
                request.writeInterfaceToken(DESCRIPTOR)
                check(binder.transact(READ_STATUS, request, reply, 0)) { "VPN status query was rejected" }
                reply.readException()
                VpnStatus.entries[reply.readInt()]
            } finally {
                request.recycle()
                reply.recycle()
            }
        }
    }

    /**
     * Asks the running VPN service to protect a socket of this process, so
     * temporary cores (latency tests) reach proxies directly instead of
     * entering the App's own tunnel and dialing the connected server through
     * itself. Without a bound service there is no tunnel to avoid. Callable
     * from any thread; it never binds.
     */
    fun protect(fd: Int): Boolean {
        val binder = connectedBinder ?: return false
        val request = Parcel.obtain()
        val reply = Parcel.obtain()
        return try {
            ParcelFileDescriptor.fromFd(fd).use { socket ->
                request.writeInterfaceToken(DESCRIPTOR)
                request.writeFileDescriptor(socket.fileDescriptor)
                binder.transact(PROTECT_SOCKET, request, reply, 0) &&
                    reply.run { readException(); readInt() == 1 }
            }
        } catch (_: Exception) {
            false
        } finally {
            request.recycle()
            reply.recycle()
        }
    }

    suspend fun changed(running: Boolean, error: String?) = withContext(Dispatchers.Main) {
        val generation = ++eventGeneration
        if (running) {
            // Subscribe to process death before acknowledging start completion.
            try { bind() } catch (failure: Exception) {
                if (generation != eventGeneration) return@withContext
                pending?.completeExceptionally(failure)
                throw failure
            }
            if (generation != eventGeneration) return@withContext
        } else {
            unbind()
        }
        if (running || error != null) VpnController.lastError = error
        val status = if (running) VpnStatus.CONNECTED else VpnStatus.DISCONNECTED
        if (status == target) pending?.complete(Unit)
        else if (!running) pending?.completeExceptionally(
            IllegalStateException(error ?: "VPN service stopped before connecting")
        )
        notify(status)
    }

    suspend fun command(wanted: VpnStatus, action: () -> Boolean): VpnStatus = withContext(Dispatchers.Main) {
        check(pending == null) { "A VPN command is already running" }
        val current = read()
        if (wanted == VpnStatus.DISCONNECTED && current == VpnStatus.DISCONNECTED) {
            check(action()) { VpnController.lastError ?: "Could not stop VPN" }
            return@withContext VpnStatus.DISCONNECTED
        }
        val completion = CompletableDeferred<Unit>()
        pending = completion
        target = wanted
        try {
            notify(if (wanted == VpnStatus.CONNECTED) VpnStatus.CONNECTING else VpnStatus.DISCONNECTING)
            check(action()) { VpnController.lastError ?: "VPN command failed" }
            withTimeout(if (wanted == VpnStatus.CONNECTED) 30_000L else 15_000L) { completion.await() }
            wanted
        } finally {
            pending = null
            target = null
        }
    }

    private suspend fun bind(): IBinder {
        service?.let { return withTimeout(3_000) { it.await() } }
        val connected = CompletableDeferred<IBinder>()
        val connection = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName, binder: IBinder) {
                if (binding === this) {
                    connectedBinder = binder
                    connected.complete(binder)
                }
            }
            override fun onServiceDisconnected(name: ComponentName) {
                if (binding !== this) return
                eventGeneration++
                val error = IllegalStateException("VPN service process exited")
                VpnController.lastError = error.message
                connected.completeExceptionally(error)
                if (target == VpnStatus.DISCONNECTED) pending?.complete(Unit)
                else pending?.completeExceptionally(error)
                unbind()
                notify(VpnStatus.DISCONNECTED)
            }
            override fun onBindingDied(name: ComponentName) = onServiceDisconnected(name)
            override fun onNullBinding(name: ComponentName) = onServiceDisconnected(name)
        }
        binding = connection
        service = connected
        try {
            // Do not create a VPN service merely to query its state.
            check(context.bindService(Intent(context, OneVpnService::class.java).setAction(ACTION_BIND), connection, 0)) {
                "Could not bind the running VPN service"
            }
            return withTimeout(3_000) { connected.await() }
        } catch (error: Exception) {
            unbind()
            throw error
        }
    }

    private fun unbind() {
        val connection = binding
        binding = null
        connectedBinder = null
        service?.takeUnless { it.isCompleted }?.cancel()
        service = null
        if (connection != null) {
            try { context.unbindService(connection) } catch (_: IllegalArgumentException) { }
        }
    }

    fun close() {
        pending?.cancel()
        unbind()
    }
}
