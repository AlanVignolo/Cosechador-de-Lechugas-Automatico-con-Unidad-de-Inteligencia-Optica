# Configuración Manual de Tubos y Cintas

## Archivos de Configuración

### 1. `configuracion_tubos.json` - Posiciones de los Tubos

Define las posiciones Y (verticales) de cada tubo.

**Formato:**
```json
{
  "metadata": {
    "version": "1.0",
    "source": "manual",
    "num_tubos": 2
  },
  "tubos": {
    "1": {
      "y_mm": 169.0,      // Posición Y del tubo 1 en milímetros
      "nombre": "Tubo 1",
      "origen": "manual"
    },
    "2": {
      "y_mm": 576.0,      // Posición Y del tubo 2 en milímetros
      "nombre": "Tubo 2",
      "origen": "manual"
    }
  }
}
```

**Para editar:**
- Cambia `y_mm` con la posición vertical deseada
- Puedes agregar más tubos con IDs "3", "4", etc.
- Actualiza `num_tubos` si agregas o quitas tubos

---

### 2. `matriz_cintas.json` - Posiciones de las Cintas

Define las posiciones X (horizontales) de cada cinta en cada tubo.

**Formato:**
```json
{
  "metadata": {
    "version": "1.0"
  },
  "tubos": {
    "1": {
      "y_mm": 169.0,      // Debe coincidir con configuracion_tubos.json
      "cintas": [
        {"id": 1, "x_mm": 96.0},    // Cinta 1: X=96mm
        {"id": 2, "x_mm": 288.0},   // Cinta 2: X=288mm
        {"id": 3, "x_mm": 496.0},   // Cinta 3: X=496mm
        {"id": 4, "x_mm": 688.0},   // Cinta 4: X=688mm
        {"id": 5, "x_mm": 880.0}    // Cinta 5: X=880mm
      ]
    },
    "2": {
      "y_mm": 576.0,
      "cintas": [
        {"id": 1, "x_mm": 83.0},
        {"id": 2, "x_mm": 274.0},
        {"id": 3, "x_mm": 474.0},
        {"id": 4, "x_mm": 675.0},
        {"id": 5, "x_mm": 871.0}
      ]
    }
  }
}
```

**Para editar:**
- Cambia `x_mm` con la posición horizontal deseada
- Puedes agregar o quitar cintas del array
- Los `id` deben ser únicos dentro de cada tubo
- `y_mm` debe coincidir con el tubo correspondiente en `configuracion_tubos.json`

---

## Cómo Usar

### Edición Manual

1. Abre los archivos `.json` con un editor de texto
2. Modifica los valores de `x_mm` o `y_mm` según necesites
3. Guarda el archivo
4. Reinicia el programa para que cargue la nueva configuración

### Valores Importantes

- **Límites del workspace**: X=[0, 1036mm], Y=[0, 834mm]
- **Posiciones recomendadas de tubos**: Separación mínima de 200mm
- **Posiciones recomendadas de cintas**: Separación mínima de 150mm

### Ejemplo de Edición

Si quieres cambiar la posición del Tubo 1 de Y=169mm a Y=200mm:

**configuracion_tubos.json:**
```json
"1": {
  "y_mm": 200.0,    // Cambiado de 169.0 a 200.0
  "nombre": "Tubo 1",
  "origen": "manual"
}
```

**matriz_cintas.json:**
```json
"1": {
  "y_mm": 200.0,    // También debe cambiar aquí
  "cintas": [
    {"id": 1, "x_mm": 96.0},
    ...
  ]
}
```

---

## Validación

El sistema mostrará la configuración cargada al inicio:

```
==================================================
CONFIGURACIÓN ACTUAL DE TUBOS
==================================================
Fuente: manual
Número de tubos: 2
--------------------------------------------------
Tubo 1: Y=169.0mm (fuente: manual)
Tubo 2: Y=576.0mm (fuente: manual)
==================================================
```

---

## Notas

- ⚠️ **Siempre haz backup** de los archivos antes de editarlos
- ⚠️ Asegúrate de que el JSON sea **válido** (usa un validador JSON online si es necesario)
- ⚠️ Los valores deben estar dentro de los **límites físicos del robot**
- 💡 El escaneo automático **sobreescribirá** estos archivos si se ejecuta
