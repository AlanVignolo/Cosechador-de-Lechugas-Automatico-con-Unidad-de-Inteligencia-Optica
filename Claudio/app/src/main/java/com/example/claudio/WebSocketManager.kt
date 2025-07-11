package com.example.claudio

import okhttp3.*
import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonObject

class WebSocketManager {
    private var webSocket: WebSocket? = null
    private var listener: WebSocketListener? = null
    private val gson = Gson()

    interface RobotStatusListener {
        fun onStatusUpdate(status: RobotStatus)
        fun onConnectionChanged(connected: Boolean)
    }

    fun connect(url: String, statusListener: DeveloperActivity) {
        val client = OkHttpClient()
        val request = Request.Builder()
            .url(url)
            .build()

        listener = object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d("WebSocket", "Conectado")
                statusListener.onConnectionChanged(true)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d("WebSocket", "Mensaje recibido: $text")
                try {
                    val message = gson.fromJson(text, JsonObject::class.java)
                    if (message.get("type").asString == "robot_status") {
                        val statusData = message.getAsJsonObject("data")
                        val status = gson.fromJson(statusData, RobotStatus::class.java)
                        statusListener.onStatusUpdate(status)
                    }
                } catch (e: Exception) {
                    Log.e("WebSocket", "Error parseando mensaje", e)
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.d("WebSocket", "Cerrando: $reason")
                statusListener.onConnectionChanged(false)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("WebSocket", "Error", t)
                statusListener.onConnectionChanged(false)
            }
        }

        webSocket = client.newWebSocket(request, listener!!)
    }

    fun disconnect() {
        webSocket?.close(1000, "Desconectado por usuario")
        webSocket = null
    }
}