"""
Script para generar diagrama de flujo del proceso de cosecha interactiva.
Genera la imagen: imagenes/diagrama_flujo_cosecha.png

Instalación (elegir UNA opción):

OPCIÓN 1 - Mermaid CLI (Recomendada - mejor calidad):
    npm install -g @mermaid-js/mermaid-cli
    pip install pillow

OPCIÓN 2 - Playwright (sin Node.js):
    pip install playwright
    playwright install chromium
"""

import os
import subprocess
import sys

# Crear directorio si no existe (dentro de Informe/)
script_dir = os.path.dirname(os.path.abspath(__file__))
imagenes_dir = os.path.join(script_dir, 'imagenes')
os.makedirs(imagenes_dir, exist_ok=True)

# Código Mermaid del diagrama - DISEÑO HORIZONTAL CON FUENTE GRANDE
mermaid_code = """%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#f5f5f5','primaryTextColor':'#000','primaryBorderColor':'#424242','lineColor':'#616161','secondaryColor':'#fafafa','tertiaryColor':'#f5f5f5','fontSize':'20px','fontFamily':'Arial, sans-serif'}}}%%

flowchart LR
    Start([INICIO]):::startEnd
    
    subgraph Inicial["INICIALIZACIÓN"]
        LoadMaps[Cargar tubos<br/>y cintas JSON]:::process
        CheckHoming{Robot<br/>homed?}:::decision
        DoHoming[Ejecutar<br/>homing]:::process
        ArmSafe[Brazo a posición<br/>segura]:::process
    end
    
    subgraph Navegacion["NAVEGACIÓN Y CLASIFICACIÓN"]
        LoopTubes[Para cada<br/>tubo]:::loop
        LoopBelts[Para cada<br/>cinta]:::loop
        Navigate[Mover a<br/>X_cinta, Y_tubo]:::process
        ClassifyIA{Clasificar IA<br/>Estado?}:::decision
        Empty[VACÍO<br/>Continuar]:::skip
        NotReady[NO LISTA<br/>Continuar]:::skip
    end
    
    subgraph Cosecha["COSECHA Y TRANSPORTE"]
        CorrectPos[Corrección<br/>posición IA]:::critical
        Pick[Recoger lechuga<br/>extender + cerrar]:::critical
        Transport[Mover lechuga<br/>con planta]:::critical
    end
    
    subgraph Deposito["DEPÓSITO"]
        MoveDeposit[Mover a zona<br/>depósito]:::process
        Deposit[Depositar lechuga<br/>inclinar + abrir]:::critical
        ReturnArm[Retornar brazo<br/>sin planta]:::critical
    end
    
    subgraph Control["CONTROL FLUJO"]
        MoreBelts{Más<br/>cintas?}:::decision
        ReturnOrigin[Volver a<br/>origen 0,0]:::process
    end
    
    End([FIN]):::startEnd
    
    Start --> LoadMaps
    LoadMaps --> CheckHoming
    CheckHoming -->|NO| DoHoming
    DoHoming --> ArmSafe
    CheckHoming -->|SÍ| ArmSafe
    ArmSafe --> LoopTubes
    LoopTubes --> LoopBelts
    LoopBelts --> Navigate
    Navigate --> ClassifyIA
    ClassifyIA -->|VACÍO| Empty
    ClassifyIA -->|NO LISTA| NotReady
    ClassifyIA -->|LISTA| CorrectPos
    CorrectPos --> Pick
    Pick --> Transport
    Transport --> MoveDeposit
    MoveDeposit --> Deposit
    Deposit --> ReturnArm
    ReturnArm --> MoreBelts
    Empty --> MoreBelts
    NotReady --> MoreBelts
    MoreBelts -->|SÍ| LoopBelts
    MoreBelts -->|NO| ReturnOrigin
    ReturnOrigin --> End
    
    classDef startEnd fill:#2E7D32,stroke:#1B5E20,stroke-width:4px,color:#fff,font-weight:bold,font-size:18px
    classDef process fill:#1565C0,stroke:#0D47A1,stroke-width:3px,color:#fff,font-weight:bold,font-size:16px
    classDef decision fill:#D84315,stroke:#BF360C,stroke-width:3px,color:#fff,font-weight:bold,font-size:16px
    classDef critical fill:#6A1B9A,stroke:#4A148C,stroke-width:3px,color:#fff,font-weight:bold,font-size:16px
    classDef skip fill:#616161,stroke:#424242,stroke-width:3px,color:#fff,font-size:16px
    classDef loop fill:#00838F,stroke:#006064,stroke-width:3px,color:#fff,font-weight:bold,font-size:16px
"""

def generar_con_mermaid_cli():
    """Opción 1: Usar Mermaid CLI (mejor calidad)"""
    print("Generando diagrama con Mermaid CLI...")

    # Guardar código Mermaid en archivo temporal
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mmd_file = os.path.join(script_dir, 'imagenes', 'temp_diagrama.mmd')
    with open(mmd_file, 'w', encoding='utf-8') as f:
        f.write(mermaid_code)

    # Generar imagen con mmdc - ALTA RESOLUCIÓN
    output_file = os.path.join(script_dir, 'imagenes', 'diagrama_flujo_cosecha.png')
    try:
        subprocess.run([
            'mmdc',
            '-i', mmd_file,
            '-o', output_file,
            '-w', '3600',   # Ancho muy grande para texto nítido
            '-H', '1800',   # Alto proporcional
            '-s', '3',      # Scale factor para mejor calidad
            '-b', 'white'   # Fondo blanco
        ], check=True)
        
        # Limpiar archivo temporal
        os.remove(mmd_file)
        
        print(f"✓ Diagrama generado exitosamente: {output_file}")
        print(f"\n  Resolución: 3600x1800 px con scale=3")
        print(f"  Tamaño de fuente: 20px (grande para nitidez)")
        print(f"\n  Para LaTeX: usa width=\\textwidth o width=0.9\\textwidth")
        return True
        
    except FileNotFoundError:
        print("✗ Error: mmdc no está instalado.")
        print("  Instala con: npm install -g @mermaid-js/mermaid-cli")
        return False
    except subprocess.CalledProcessError as e:
        print(f"✗ Error al generar diagrama: {e}")
        return False

def generar_con_playwright():
    """Opción 2: Usar Playwright (sin necesitar Node.js)"""
    print("Generando diagrama con Playwright...")

    try:
        from playwright.sync_api import sync_playwright

        # HTML con el diagrama Mermaid - FUENTE GRANDE
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script type="module">
                import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                mermaid.initialize({{ 
                    startOnLoad: true, 
                    theme: 'base',
                    fontSize: 20
                }});
            </script>
            <style>
                body {{
                    margin: 0;
                    padding: 60px;
                    background: white;
                    display: flex;
                    justify-content: center;
                    align-items: flex-start;
                }}
                .mermaid {{
                    max-width: 100%;
                    font-size: 20px;
                }}
                .mermaid svg {{
                    font-size: 20px !important;
                }}
            </style>
        </head>
        <body>
            <div class="mermaid">
{mermaid_code}
            </div>
        </body>
        </html>
        """

        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(script_dir, 'imagenes', 'diagrama_flujo_cosecha.png')

        with sync_playwright() as p:
            browser = p.chromium.launch()
            # VIEWPORT MUY GRANDE + DEVICE SCALE FACTOR ALTO = TEXTO NÍTIDO
            page = browser.new_page(
                viewport={'width': 6000, 'height': 3000}, 
                device_scale_factor=3  # Factor 3 para máxima nitidez
            )
            page.set_content(html_content)

            # Esperar más tiempo para renderizado completo
            page.wait_for_timeout(4000)

            # Capturar screenshot del diagrama
            diagram = page.locator('.mermaid svg')
            diagram.screenshot(
                path=output_file,
                type='png',
                omit_background=False
            )

            browser.close()

        print(f"✓ Diagrama generado exitosamente: {output_file}")
        print(f"\n  Viewport: 6000x3000 px")
        print(f"  Device scale factor: 3 (resolución efectiva: 18000x9000 px)")
        print(f"  Tamaño de fuente: 20px (grande para nitidez)")
        print(f"\n  Para LaTeX: usa width=\\textwidth o width=0.9\\textwidth")
        return True

    except ImportError:
        print("✗ Error: playwright no está instalado.")
        print("  Instala con: pip install playwright")
        print("  Luego ejecuta: playwright install chromium")
        return False
    except Exception as e:
        print(f"✗ Error al generar diagrama: {e}")
        return False

def main():
    print("=" * 70)
    print("  Generador de Diagrama de Flujo - Cosecha Interactiva")
    print("  FORMATO HORIZONTAL - ALTA RESOLUCIÓN PARA TEXTO NÍTIDO")
    print("=" * 70)
    
    # Intentar primero con Mermaid CLI
    if generar_con_mermaid_cli():
        return
    
    print("\nIntentando método alternativo con Playwright...")
    if generar_con_playwright():
        return
    
    print("\n" + "=" * 70)
    print("No se pudo generar el diagrama. Por favor instala:")
    print("\nOPCIÓN 1 (Recomendada):")
    print("  npm install -g @mermaid-js/mermaid-cli")
    print("\nOPCIÓN 2 (Alternativa):")
    print("  pip install playwright")
    print("  playwright install chromium")
    print("=" * 70)

if __name__ == "__main__":
    main()