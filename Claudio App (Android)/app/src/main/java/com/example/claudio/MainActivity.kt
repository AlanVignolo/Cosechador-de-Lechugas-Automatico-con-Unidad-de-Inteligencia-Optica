package com.example.claudio

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private var lechugasCosechadas = 0
    private var tiempoMedioCrecimiento = "45 días"
    private var cantidadLechugasSeccion1 = 5
    private var cantidadLechugasSeccion2 = 5
    private lateinit var tvEstadoSistema: TextView

    private var estadosSeccion1 = intArrayOf(2, 1, 2, 0, 1)
    private var estadosSeccion2 = intArrayOf(1, 2, 1, 2, 0)

    private lateinit var tvLechugasCosechadas: TextView
    private lateinit var tvTiempoMedio: TextView
    private lateinit var layoutSeccion1: LinearLayout
    private lateinit var layoutSeccion2: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        initViews()
        setupLechugaLayouts()
        setupButtons()
        updateUI()
    }

    private fun initViews() {
        tvLechugasCosechadas = findViewById(R.id.tv_lechugas_cosechadas)
        tvTiempoMedio = findViewById(R.id.tv_tiempo_medio)
        layoutSeccion1 = findViewById(R.id.layout_seccion1)
        layoutSeccion2 = findViewById(R.id.layout_seccion2)
        tvEstadoSistema = findViewById(R.id.tv_estado_sistema)
    }

    private fun setupLechugaLayouts() {
        layoutSeccion1.removeAllViews()
        for (i in 0 until cantidadLechugasSeccion1) {
            val lechugaView = createLechugaView(estadosSeccion1[i])
            layoutSeccion1.addView(lechugaView)
        }

        layoutSeccion2.removeAllViews()
        for (i in 0 until cantidadLechugasSeccion2) {
            val lechugaView = createLechugaView(estadosSeccion2[i])
            layoutSeccion2.addView(lechugaView)
        }
    }

    private fun createLechugaView(estado: Int): TextView {
        val lechugaView = TextView(this)

        val params = LinearLayout.LayoutParams(120, 120)
        params.setMargins(8, 8, 8, 8)
        lechugaView.layoutParams = params

        when (estado) {
            0 -> {
                lechugaView.setBackgroundColor(ContextCompat.getColor(this, R.color.negro))
                lechugaView.text = "●"
                lechugaView.setTextColor(ContextCompat.getColor(this, R.color.blanco))
            }
            1 -> {
                lechugaView.setBackgroundColor(ContextCompat.getColor(this, R.color.amarillo_claro))
                lechugaView.text = "🥬"
            }
            2 -> {
                lechugaView.setBackgroundColor(ContextCompat.getColor(this, R.color.verde_lechuga))
                lechugaView.text = "🥬"
            }
        }

        lechugaView.textAlignment = TextView.TEXT_ALIGNMENT_CENTER
        lechugaView.textSize = 20f
        lechugaView.setPadding(8, 8, 8, 8)

        return lechugaView
    }

    private fun setupButtons() {
        val btnHistorial: Button = findViewById(R.id.btn_historial)
        val btnEscanear: Button = findViewById(R.id.btn_escanear)
        val btnReferenciar: Button = findViewById(R.id.btn_referenciar)
        val btnFrenar: Button = findViewById(R.id.btn_frenar)
        val btnApagar: Button = findViewById(R.id.btn_apagar)
        val btnDesarrollador: Button = findViewById(R.id.btn_desarrollador)

        btnHistorial.setOnClickListener {
            Toast.makeText(this, "Abriendo historial...", Toast.LENGTH_SHORT).show()
        }

        btnEscanear.setOnClickListener {
            escanear()
        }

        btnReferenciar.setOnClickListener {
            referenciar()
        }

        btnFrenar.setOnClickListener {
            frenar()
        }

        btnApagar.setOnClickListener {
            apagar()
        }

        btnDesarrollador.setOnClickListener {
            val intent = Intent(this, DeveloperActivity::class.java)
            startActivity(intent)
        }
    }

    private fun updateUI() {
        tvLechugasCosechadas.text = "Lechugas cosechadas: $lechugasCosechadas"
        tvTiempoMedio.text = "Tiempo medio: $tiempoMedioCrecimiento"
        tvEstadoSistema.text = "Conectado"
        tvEstadoSistema.setTextColor(ContextCompat.getColor(this, R.color.verde_lechuga))
    }

    private fun escanear() {
        Toast.makeText(this, "Escaneando jardín...", Toast.LENGTH_SHORT).show()
    }

    private fun referenciar() {
        Toast.makeText(this, "Referenciando sistema...", Toast.LENGTH_SHORT).show()
    }

    private fun frenar() {
        Toast.makeText(this, "Frenando sistema...", Toast.LENGTH_SHORT).show()
    }

    private fun apagar() {
        Toast.makeText(this, "Apagando sistema...", Toast.LENGTH_SHORT).show()
    }

    fun actualizarEstados(seccion1: IntArray, seccion2: IntArray, cosechadas: Int, tiempo: String) {
        estadosSeccion1 = seccion1
        estadosSeccion2 = seccion2
        lechugasCosechadas = cosechadas
        tiempoMedioCrecimiento = tiempo

        runOnUiThread {
            setupLechugaLayouts()
            updateUI()
        }
    }
}