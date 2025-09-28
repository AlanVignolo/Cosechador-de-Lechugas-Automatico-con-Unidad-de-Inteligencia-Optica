# Detector de Tubos Verticales - Robot CLAUDIO

Sistema de detección de tubos blancos opacos para el escáner vertical del robot CLAUDIO.

## Archivos Principales

- **`tube_detector_vertical.py`**: Módulo principal de detección con funciones de debug
- **`test_tube_detection.py`**: Suite de tests para calibración y ajuste de parámetros
- **`escaner_vertical.py`**: Escáner vertical existente (manual)

## Características del Sistema

### Detección Específica para Tubos
- **Objetivo**: Detectar tubos blancos opacos con tapas brillantes
- **Método**: Detección de líneas horizontales características del tubo
- **Orientación**: Sin rotación de imagen (mantiene orientación original)
- **Debug Visual**: Paso a paso para ajustar filtros

### Diferencias vs Detección Horizontal
| Aspecto | Horizontal (Cintas) | Vertical (Tubos) |
|---------|-------------------|------------------|
| **Objeto** | Cintas oscuras | Tubos blancos opacos |
| **Filtro** | Threshold inverso (oscuros) | Threshold directo (claros) |
| **Forma** | Líneas verticales alargadas | Líneas horizontales + formas cilíndricas |
| **Rotación** | 90° anti-horario | Sin rotación |
| **Scoring** | Consistencia + rectitud | Brillo + forma + posición central |

## Uso del Sistema

### 1. Test Básico de Conexión
```python
from test_tube_detection import test_camera_connection
test_camera_connection()
```

### 2. Test de Detección Simple
```python
from test_tube_detection import test_detection_simple
test_detection_simple()
```

### 3. Test con Debug Visual Completo
```python
from test_tube_detection import test_detection_debug  
test_detection_debug()
```

### 4. Menú Interactivo Completo
```python
python test_tube_detection.py
```

## Algoritmo de Detección

### Paso 1: Preparación de Imagen
- Captura sin rotación (orientación original)
- Recorte ROI: 20%-80% horizontal, 30%-70% vertical
- Conversión a espacios de color: Gray, HSV

### Paso 2: Filtros para Tubos Blancos
1. **Blancos Brillantes**: HSV con alto brillo (V>180) y baja saturación (S<50)
2. **Brillo Alto**: Threshold en canal V del HSV (>160)
3. **Baja Saturación**: Threshold inverso en canal S (<40)
4. **Blanco Opaco**: Combinación de brillo alto + baja saturación
5. **Threshold Claro**: Threshold simple en escala de grises (>140)

### Paso 3: Evaluación de Candidatos
**Scoring basado en:**
- **Área**: 200-5000 píxeles (tamaño razonable)
- **Solidez**: Extent > 0.3 (forma compacta)
- **Posición Central**: Dentro del 30% central de la imagen
- **Tamaño Apropiado**: 30-200px ancho, 30-300px alto

### Paso 4: Selección Final
- Ordenar candidatos por score
- Retornar coordenada Y del centro del mejor candidato

## Calibración de Parámetros

### Parámetros Ajustables en `tube_detector_vertical.py`:

```python
# Filtro blancos brillantes
lower_white = np.array([0, 0, 180])      # HSV mínimo
upper_white = np.array([180, 50, 255])   # HSV máximo

# Threshold de brillo
brillo_threshold = 160

# Threshold de saturación
saturacion_threshold = 40

# Threshold escala de grises
gray_threshold = 140

# Filtros de área
area_min = 200
area_max = 5000

# Scoring
area_score_weight = 10
solidity_score_weight = 10  
center_score_weight = 15
size_score_weight = 10
```

### Proceso de Calibración:

1. **Ejecutar test con debug**: `python test_tube_detection.py` → opción 4
2. **Revisar imágenes mostradas**: Verificar qué filtros detectan mejor los tubos
3. **Ajustar parámetros**: Modificar valores en `tube_detector_vertical.py`
4. **Probar configuraciones**: Usar opción 5 del menú para test interactivo
5. **Validar resultados**: Repetir hasta obtener detección consistente

### Problemas Comunes y Soluciones:

| Problema | Causa Posible | Solución |
|----------|---------------|----------|
| No detecta tubos | Filtros muy estrictos | Bajar thresholds, aumentar rango HSV |
| Muchos falsos positivos | Filtros muy permisivos | Subir thresholds, reducir área máxima |
| Detección inconsistente | Iluminación variable | Usar múltiples filtros, ajustar scoring |
| Posición incorrecta | Mal scoring de candidatos | Ajustar pesos del scoring |

## Integración con Escáner Vertical

### Para usar en el escáner autónomo:

1. **Importar detector**:
```python
from tube_detector_vertical import detect_tube_position
```

2. **Integrar en loop de detección**:
```python
def detect_tube_in_frame(frame):
    # Procesar frame (sin rotación para tubos)
    processed_frame = frame[y1:y2, x1:x2]  # Solo recorte
    
    # Detectar tubo
    tube_y = detect_tube_position(processed_frame, debug=False)
    
    return tube_y is not None
```

3. **Usar en sistema de flags**:
```python
is_tube_detected = detect_tube_in_frame(current_frame)
process_detection_state(is_tube_detected)
```

## Próximos Pasos

1. **Calibrar parámetros** con tubos reales del sistema
2. **Crear escáner vertical autónomo** basado en `escaner_standalone.py`
3. **Integrar con configuracion_tubos.py** para actualizar posiciones Y
4. **Probar detección en diferentes condiciones** de iluminación
5. **Optimizar algoritmo** según resultados de campo

## Notas Técnicas

- **Sin rotación**: Los tubos se ven naturalmente verticales en la imagen
- **Filtros invertidos**: Detectamos objetos claros en lugar de oscuros
- **Debug extensivo**: Cada paso del algoritmo es visualizable
- **Compatibilidad**: Misma interfaz que el detector horizontal
- **Flexibilidad**: Múltiples filtros y scoring adaptativo

## Contacto

Para reportar problemas o sugerir mejoras en el sistema de detección de tubos.
