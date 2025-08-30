package com.example.claudio

import android.os.Bundle
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class DeveloperActivity : AppCompatActivity() {

    private lateinit var tvServo1: TextView
    private lateinit var tvServo2: TextView
    private lateinit var tvEstadoBrazo: TextView
    private lateinit var tvGripper: TextView
    private lateinit var tvPosicionX: TextView
    private lateinit var tvPosicionY: TextView
    private lateinit var tvMaxX: TextView
    private lateinit var tvMaxY: TextView
    private lateinit var tvComunicacion: TextView

    private lateinit var etMoverX: EditText
    private lateinit var etMoverY: EditText
    private lateinit var etServo1: EditText
    private lateinit var etServo2: EditText
    private lateinit var etTiempo: EditText
    private lateinit var spinnerEstados: Spinner

    private lateinit var webSocketManager: WebSocketManager

    private lateinit var robotRepository: RobotRepository

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_developer)

        robotRepository = RobotRepository()
        webSocketManager = WebSocketManager()

        initViews()
        setupSpinner()
        setupButtons()
        updateRobotStatus()
        connectWebSocket()
    }

    private fun initViews() {
        tvServo1 = findViewById(R.id.tv_servo1)
        tvServo2 = findViewById(R.id.tv_servo2)
        tvEstadoBrazo = findViewById(R.id.tv_estado_brazo)
        tvGripper = findViewById(R.id.tv_gripper)
        tvPosicionX = findViewById(R.id.tv_posicion_x)
        tvPosicionY = findViewById(R.id.tv_posicion_y)
        tvMaxX = findViewById(R.id.tv_max_x)
        tvMaxY = findViewById(R.id.tv_max_y)
        tvComunicacion = findViewById(R.id.tv_comunicacion)

        etMoverX = findViewById(R.id.et_mover_x)
        etMoverY = findViewById(R.id.et_mover_y)
        etServo1 = findViewById(R.id.et_servo1)
        etServo2 = findViewById(R.id.et_servo2)
        etTiempo = findViewById(R.id.et_tiempo)
        spinnerEstados = findViewById(R.id.spinner_estados)
    }

    private fun connectWebSocket() {
        val wsUrl = "ws://192.168.100.2:8000/ws"
        webSocketManager.connect(wsUrl, this)
    }

    override fun onDestroy() {
        super.onDestroy()
        webSocketManager.disconnect()
    }

    fun onStatusUpdate(status: RobotStatus) {
        runOnUiThread {
            updateUIWithStatus(status)
        }
    }

    fun onConnectionChanged(connected: Boolean) {
        runOnUiThread {
            updateCommunicationStatus(connected)
        }
    }

    private fun setupSpinner() {
        val estados = arrayOf(
            "movimiento",
            "recoger_lechuga",
            "mover_lechuga",
            "depositar_lechuga"
        )

        val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, estados)
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        spinnerEstados.adapter = adapter
    }

    private fun setupButtons() {
        val btnMoverXY: Button = findViewById(R.id.btn_mover_xy)
        val btnHoming: Button = findViewById(R.id.btn_homing)
        val btnReferenciaCompleta: Button = findViewById(R.id.btn_referencia_completa)
        val btnGripperAbrir: Button = findViewById(R.id.btn_gripper_abrir)
        val btnGripperCerrar: Button = findViewById(R.id.btn_gripper_cerrar)
        val btnMovimientoSuave: Button = findViewById(R.id.btn_movimiento_suave)
        val btnIrEstado: Button = findViewById(R.id.btn_ir_estado)
        val btnEmergencia: Button = findViewById(R.id.btn_emergencia)
        val btnActualizar: Button = findViewById(R.id.btn_actualizar)

        btnMoverXY.setOnClickListener { moverXY() }
        btnHoming.setOnClickListener { homing() }
        btnReferenciaCompleta.setOnClickListener { referenciaCompleta() }
        btnGripperAbrir.setOnClickListener { gripperAbrir() }
        btnGripperCerrar.setOnClickListener { gripperCerrar() }
        btnMovimientoSuave.setOnClickListener { movimientoSuave() }
        btnIrEstado.setOnClickListener { irEstado() }
        btnEmergencia.setOnClickListener { emergencia() }
        btnActualizar.setOnClickListener { updateRobotStatus() }
    }

    private fun moverXY() {
        val xText = etMoverX.text.toString()
        val yText = etMoverY.text.toString()

        if (xText.isNotEmpty() && yText.isNotEmpty()) {
            try {
                val x = xText.toDouble()
                val y = yText.toDouble()

                showProgress("Moviendo a X:$x, Y:$y...")

                robotRepository.moveToPosition(x, y) { response, error ->
                    runOnUiThread {
                        hideProgress()
                        if (error != null) {
                            showError("Error moviendo: $error")
                        } else {
                            showSuccess("Movimiento iniciado: ${response?.message}")
                            updateRobotStatus()
                        }
                    }
                }
            } catch (e: NumberFormatException) {
                showError("Valores X e Y deben ser números válidos")
            }
        } else {
            showError("Ingrese valores X e Y")
        }
    }

    private fun homing() {
        showProgress("Ejecutando homing...")

        robotRepository.homeRobot { response, error ->
            runOnUiThread {
                hideProgress()
                if (error != null) {
                    showError("Error en homing: $error")
                } else {
                    showSuccess("Homing completado: ${response?.message}")
                    updateRobotStatus()
                }
            }
        }
    }

    private fun referenciaCompleta() {
        showProgress("Ejecutando referencia completa...")

        robotRepository.calibrateWorkspace { response, error ->
            runOnUiThread {
                hideProgress()
                if (error != null) {
                    showError("Error en calibración: $error")
                } else {
                    showSuccess("Calibración completada: ${response?.message}")
                    updateRobotStatus()
                }
            }
        }
    }

    private fun gripperAbrir() {
        showProgress("Abriendo gripper...")

        robotRepository.openGripper { response, error ->
            runOnUiThread {
                hideProgress()
                if (error != null) {
                    showError("Error abriendo gripper: $error")
                } else {
                    showSuccess("Gripper: ${response?.message}")
                    updateRobotStatus()
                }
            }
        }
    }

    private fun gripperCerrar() {
        showProgress("Cerrando gripper...")

        robotRepository.closeGripper { response, error ->
            runOnUiThread {
                hideProgress()
                if (error != null) {
                    showError("Error cerrando gripper: $error")
                } else {
                    showSuccess("Gripper: ${response?.message}")
                    updateRobotStatus()
                }
            }
        }
    }

    private fun movimientoSuave() {
        val servo1Text = etServo1.text.toString()
        val servo2Text = etServo2.text.toString()
        val tiempoText = etTiempo.text.toString()

        if (servo1Text.isNotEmpty() && servo2Text.isNotEmpty() && tiempoText.isNotEmpty()) {
            try {
                val servo1 = servo1Text.toInt()
                val servo2 = servo2Text.toInt()
                val tiempo = tiempoText.toInt()

                if (servo1 in 0..180 && servo2 in 0..180) {
                    showProgress("Ejecutando movimiento suave...")

                    robotRepository.moveArm(servo1, servo2, tiempo) { response, error ->
                        runOnUiThread {
                            hideProgress()
                            if (error != null) {
                                showError("Error moviendo brazo: $error")
                            } else {
                                showSuccess("Movimiento iniciado: ${response?.message}")
                                updateRobotStatus()
                            }
                        }
                    }
                } else {
                    showError("Servos deben estar entre 0 y 180 grados")
                }
            } catch (e: NumberFormatException) {
                showError("Valores deben ser números válidos")
            }
        } else {
            showError("Complete todos los campos")
        }
    }

    private fun irEstado() {
        val estadoSeleccionado = spinnerEstados.selectedItem.toString()
        showProgress("Cambiando a estado: $estadoSeleccionado...")

        robotRepository.changeArmState(estadoSeleccionado) { response, error ->
            runOnUiThread {
                hideProgress()
                if (error != null) {
                    showError("Error cambiando estado: $error")
                } else {
                    showSuccess("Estado cambiado: ${response?.message}")
                    updateRobotStatus()
                }
            }
        }
    }

    private fun emergencia() {
        showProgress("EJECUTANDO PARADA DE EMERGENCIA...")

        robotRepository.emergencyStop { response, error ->
            runOnUiThread {
                hideProgress()
                if (error != null) {
                    showError("Error en parada de emergencia: $error")
                } else {
                    showSuccess("SISTEMA DETENIDO: ${response?.message}")
                    updateRobotStatus()
                }
            }
        }
    }

    private fun updateRobotStatus() {
        showProgress("Actualizando estado...")

        robotRepository.getRobotStatus { status, error ->
            runOnUiThread {
                hideProgress()
                if (error != null) {
                    showError("Error obteniendo estado: $error")
                    updateCommunicationStatus(false)
                } else if (status != null) {
                    updateUIWithStatus(status)
                    updateCommunicationStatus(true)
                }
            }
        }
    }

    private fun updateUIWithStatus(status: RobotStatus) {
        tvServo1.text = "Servo 1: ${status.arm.servo1}°"
        tvServo2.text = "Servo 2: ${status.arm.servo2}°"
        tvEstadoBrazo.text = "Estado: ${getCurrentArmState()}"
        tvGripper.text = "Gripper: ${status.gripper}"
        tvPosicionX.text = "X actual: ${String.format("%.1f", status.position.x)} mm"
        tvPosicionY.text = "Y actual: ${String.format("%.1f", status.position.y)} mm"
        tvMaxX.text = "X máx: 1800 mm"
        tvMaxY.text = "Y máx: 1000 mm"
    }

    private fun getCurrentArmState(): String {
        // Se podría obtener del status si se agrega al API
        return "detectando..."
    }

    private fun updateCommunicationStatus(isConnected: Boolean) {
        if (isConnected) {
            tvComunicacion.text = "Comunicación: ACTIVA"
            tvComunicacion.setTextColor(ContextCompat.getColor(this, R.color.verde_lechuga))
        } else {
            tvComunicacion.text = "Comunicación: INACTIVA"
            tvComunicacion.setTextColor(ContextCompat.getColor(this, R.color.rojo_apagar))
        }
    }

    private fun showProgress(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }

    private fun hideProgress() {
        // Se podría implementar un ProgressDialog si se quiere
    }

    private fun showError(message: String) {
        Toast.makeText(this, "❌ $message", Toast.LENGTH_LONG).show()
    }

    private fun showSuccess(message: String) {
        Toast.makeText(this, "✅ $message", Toast.LENGTH_SHORT).show()
    }
}