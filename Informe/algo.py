import os

# Estructura de directorios y archivos
estructura = {
    "00_Resumen": ["resumen"],
    "01_Introduccion": ["contexto_motivacion", "objetivos", "alcance_limitaciones", "estructura_documento"],
    "02_MarcoTeorico/2.1_control_jerarquico": ["arquitecturas_multinivel", "supervisorio_vs_regulatorio", "fundamentacion_separacion", "ventajas_arquitectura"],
    "02_MarcoTeorico/2.2_vision_ia": ["procesamiento_imagenes", "redes_convolucionales", "transfer_learning", "metricas_evaluacion"],
    "02_MarcoTeorico/2.3_cinematica": ["modelado_cinematico", "espacios_trabajo", "analisis_trayectorias"],
    "02_MarcoTeorico/2.4_transmision": ["correa_poleas", "husillo_tuerca", "rodamientos_guias"],
    "02_MarcoTeorico/2.5_motores": ["principio_funcionamiento", "modos_operacion", "drivers_electronica"],
    "03_Desarrollo/3.1_arquitectura_general": ["diagrama_bloques", "interaccion_niveles", "flujo_informacion", "maquina_estados_global"],
    "03_Desarrollo/3.2_modelado_mecanico": ["especificaciones_diseno", "grados_libertad", "ecuaciones_movimiento", "espacio_trabajo", 
                                             "seleccion_materiales", "calculos_resistencia", "estructura_soporte", "dimensionamiento_correa", 
                                             "seleccion_poleas", "calculo_cargas_horizontal", "analisis_husillo", "calculo_torque", 
                                             "seleccion_guias", "configuracion_brazo", "cinematica_brazo", "seleccion_servos", 
                                             "diseno_piezas_3d", "tecnologia_impresion", "tolerancias_ajustes"],
    "03_Desarrollo/3.3_nivel_regulatorio": ["arquitectura_regulatorio", "justificacion_arduino", "distribucion_pines", "motores_paso_paso", 
                                             "drivers_tb6600", "servomotores", "finales_carrera", "sistema_seguridad", 
                                             "generacion_trayectorias", "control_velocidad", "conversion_pasos_mm", 
                                             "estructura_comandos", "manejo_errores"],
    "03_Desarrollo/3.4_nivel_supervisor": ["arquitectura_supervisor", "justificacion_raspberry", "capacidades_limitaciones", 
                                            "diagrama_estados", "transiciones_condiciones", "manejo_excepciones", 
                                            "gestion_comandos", "sincronizacion_movimientos", "recuperacion_fallas"],
    "03_Desarrollo/3.5_ia_vision": ["arquitectura_ia", "pipeline_procesamiento", "hardware_camara", "preprocesamiento", 
                                     "analisis_morfologico", "calibracion_pixel_mm", "ecuaciones_transformacion", 
                                     "validacion_estadistica", "arquitectura_cnn", "funcion_perdida", "metricas_desempeno", 
                                     "justificacion_arquitectura", "algoritmo_exploracion", "sincronizacion_imagen_posicion", 
                                     "cooldown_espacial", "matriz_cultivo", "tsp_adaptado", "funcion_objetivo", "heuristicas", 
                                     "correccion_horizontal_vertical", "criterio_convergencia", "precision_alcanzada", 
                                     "arquitectura_modular", "logging_monitoreo", "calibracion_automatica"],
    "03_Desarrollo/3.6_interfaz": ["diseno_interfaz", "funcionalidades", "visualizacion_datos", "control_remoto"],
    "03_Desarrollo/3.7_montaje": ["ensamblaje_mecanico", "integracion_electronica", "calibracion_puesta_marcha", "problemas_soluciones"],
    "04_Pruebas/4.1_metodologia": ["diseno_experimental", "metricas_evaluacion"],
    "04_Pruebas/4.2_mecanico": ["precision_posicionamiento", "repetibilidad", "velocidades_maximas", "vibraciones_estabilidad"],
    "04_Pruebas/4.3_control": ["respuesta_temporal", "manejo_errores", "finales_carrera"],
    "04_Pruebas/4.4_ia": ["precision_deteccion", "tasa_clasificacion", "tiempo_procesamiento", "robustez_variaciones", "validacion_mapeo"],
    "04_Pruebas/4.5_integracion": ["ciclo_completo", "eficiencia_sistema", "casos_extremos"],
    "04_Pruebas/4.6_analisis": ["comparacion_objetivos", "limitaciones", "mejoras_potenciales"],
    "05_Conclusiones/5.1_conclusiones": ["logros_alcanzados", "cumplimiento_objetivos", "lecciones_aprendidas"],
    "05_Conclusiones/5.2_aportes": ["innovaciones", "contribuciones_tecnicas"],
    "05_Conclusiones/5.3_trabajo_futuro": ["mejoras_propuestas", "escalabilidad", "aplicaciones_potenciales"],
    "Anexos": ["A_diagramas_electricos", "B_codigo_fuente", "C_especificaciones", "D_manual_usuario", "E_hojas_datos"],
    "Referencias": ["referencias"],
}

# Crear carpeta imagenes
os.makedirs("imagenes", exist_ok=True)

# Crear estructura
for carpeta, archivos in estructura.items():
    os.makedirs(carpeta, exist_ok=True)
    for archivo in archivos:
        ruta_archivo = os.path.join(carpeta, f"{archivo}.tex")
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            f.write(f"% {archivo.replace('_', ' ').title()}\n\n")
        print(f"✓ Creado: {ruta_archivo}")

print("\n¡Estructura completa creada exitosamente!")