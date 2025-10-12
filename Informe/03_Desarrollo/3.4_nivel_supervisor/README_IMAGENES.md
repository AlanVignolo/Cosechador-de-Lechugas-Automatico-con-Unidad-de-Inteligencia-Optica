# Imágenes Requeridas para Sección 3.5 - Nivel Supervisor

## 1. Arquitectura Supervisor Modular
**Archivo:** `arquitectura_supervisor_modular.png`
**Ubicación:** `Informe/imagenes/`
**Referencia:** Figura \ref{fig:arquitectura_supervisor_modular}

### Descripción:
Diagrama de bloques mostrando la arquitectura modular del Nivel Supervisor.

### Elementos a incluir:
- **5 módulos principales** (cajas con bordes):
  1. **Core** (RobotController, CameraManager)
  2. **Hardware** (UARTManager, CommandManager)
  3. **Robot** (ArmController, Trajectories, ArmStates)
  4. **Workflows** (inicio_completo, inicio_simple, cosecha_interactiva)
  5. **Config** (RobotConfig)

- **Conexiones entre módulos** (flechas):
  - Core ↔ Hardware (comunicación bidireccional)
  - Core ↔ Robot (control de brazo)
  - Workflows → Core (orquestación)
  - Workflows → Robot (control directo)
  - Config → Todos (parámetros)

- **Interfaces externas**:
  - Hardware → Arduino (UART)
  - Core → Cámara USB
  - Workflows → Módulos IA

### Sugerencia de herramienta:
- Draw.io / diagrams.net
- PowerPoint con SmartArt
- Inkscape (SVG vectorial)

---

## 2. Diagrama de Estados del Brazo
**Archivo:** `diagrama_estados_brazo.png`
**Ubicación:** `Informe/imagenes/`
**Referencia:** Figura \ref{fig:estados_brazo}

### Descripción:
Máquina de estados finitos (FSM) del brazo robótico con transiciones.

### Elementos a incluir:
- **4 estados** (círculos o rectángulos redondeados):
  1. `movimiento` (10°, 10°)
  2. `recoger_lechuga` (100°, 80°)
  3. `mover_lechuga` (50°, 160°)
  4. `depositar_lechuga` (90°, 20°)

- **Transiciones permitidas** (flechas direccionales):
  - movimiento → recoger_lechuga
  - recoger_lechuga → movimiento
  - recoger_lechuga → mover_lechuga
  - mover_lechuga → movimiento
  - mover_lechuga → depositar_lechuga
  - depositar_lechuga → movimiento
  - depositar_lechuga → mover_lechuga

- **Condiciones de guarda** (texto sobre flechas):
  - Ejemplo: "lettuce_present = False" para ciertas transiciones
  - Ejemplo: "XY idle" para transiciones desde movimiento

- **Colores sugeridos**:
  - Estado seguro (movimiento): Verde
  - Estados operativos: Azul
  - Transiciones: Negro/Gris

### Sugerencia de herramienta:
- Draw.io (tiene templates de FSM)
- yEd
- Graphviz (programático)

---

## 3. Flujo de Comunicación UART (OPCIONAL - Recomendado)
**Archivo:** `flujo_comunicacion_uart.png`
**Ubicación:** `Informe/imagenes/`

### Descripción:
Diagrama de secuencia mostrando la comunicación entre Supervisor y Regulatorio.

### Elementos a incluir:
- **2 actores**:
  - Supervisor (Raspberry Pi)
  - Regulatorio (Arduino)

- **Ejemplo de secuencia**:
  1. Supervisor → Arduino: `<M:50.0,-20.0>`
  2. Arduino → Supervisor: `<RESPONSE:OK>`
  3. [Arduino ejecuta movimiento]
  4. Arduino → Supervisor: `<STEPPER_MOVE_COMPLETED:...>`
  5. Supervisor actualiza posición global

### Sugerencia de herramienta:
- PlantUML (secuencia)
- Mermaid
- Draw.io

---

## 4. Workflow de Cosecha (OPCIONAL - Muy recomendado)
**Archivo:** `workflow_cosecha_secuencia.png`
**Ubicación:** `Informe/imagenes/`

### Descripción:
Diagrama de flujo del workflow completo de cosecha de una lechuga.

### Elementos a incluir:
- **Secuencia de pasos**:
  1. Mover XY a posición de lechuga
  2. Esperar completado movimiento
  3. Cambiar brazo a 'recoger_lechuga'
  4. Cerrar gripper
  5. Cambiar brazo a 'mover_lechuga'
  6. Mover XY a depósito
  7. Cambiar brazo a 'depositar_lechuga'
  8. Abrir gripper
  9. Cambiar brazo a 'movimiento'

- **Decisiones** (rombos):
  - ¿Movimiento XY completado?
  - ¿Brazo en posición?
  - ¿Gripper cerrado?

### Sugerencia de herramienta:
- Lucidchart
- Draw.io
- Microsoft Visio

---

## Prioridad de Imágenes:

1. **ALTA PRIORIDAD** (esenciales para claridad):
   - ✅ arquitectura_supervisor_modular.png
   - ✅ diagrama_estados_brazo.png

2. **MEDIA PRIORIDAD** (mejoran comprensión):
   - flujo_comunicacion_uart.png
   - workflow_cosecha_secuencia.png

3. **BAJA PRIORIDAD** (opcionales):
   - Tabla comparativa Raspberry Pi vs alternativas (puede quedar solo texto)
   - Timeline de recuperación de fallas

---

## Dimensiones Recomendadas:
- Ancho: 1200-1600 px
- Alto: 800-1200 px
- Formato: PNG (transparente) o PDF vectorial
- DPI: 300 (para impresión)

## Estilo Visual:
- **Colores**: Paleta profesional (azul, gris, verde para estados seguros)
- **Fuentes**: Sans-serif legible (Arial, Helvetica)
- **Líneas**: Grosor medio, flechas claras
- **Espacio**: Suficiente padding entre elementos
