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

# Código Mermaid del diagrama - LAYOUT VERTICAL COMPACTO CON NODOS A LOS COSTADOS
mermaid_code = """%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#f5f5f5','primaryTextColor':'#000','primaryBorderColor':'#424242','lineColor':'#616161','secondaryColor':'#fafafa','tertiaryColor':'#f5f5f5'}}}%%

flowchart TB
    Start([INICIO]):::startEnd
    LoadMaps[Cargar tubos y cintas JSON]:::process
    CheckHoming{¿Robot homed?}:::decision

    %% Nodos a los costados de CheckHoming
    DoHoming[Ejecutar homing]:::process
    ArmSafe[Brazo → posición segura]:::process

    %% Loops lado a lado
    LoopTubes[Para cada tubo]:::loop
    LoopBelts[Para cada cinta]:::loop
    Navigate[Mover a X_cinta, Y_tubo]:::process

    ClassifyIA{Clasificar IA: ¿Estado?}:::decision

    %% Tres ramas lado a lado
    Empty[VACÍO<br/>Continuar]:::skip
    NotReady[NO LISTA<br/>Continuar]:::skip
    CorrectPos[Corrección posición IA]:::critical

    %% Proceso de cosecha en fila horizontal
    Pick[Recoger lechuga]:::critical
    Transport[Transportar]:::critical
    MoveDeposit[Mover a depósito]:::process
    Deposit[Depositar lechuga]:::critical
    ReturnArm[Retornar brazo]:::critical

    MoreBelts{¿Más cintas?}:::decision
    ReturnOrigin[Volver a origen 0,0]:::process
    End([FIN]):::startEnd

    %% Conexiones
    Start --> LoadMaps --> CheckHoming
    CheckHoming -->|NO| DoHoming --> ArmSafe
    CheckHoming -->|SÍ| ArmSafe

    ArmSafe --> LoopTubes --> LoopBelts --> Navigate --> ClassifyIA

    %% Ramificación horizontal de los 3 casos
    ClassifyIA -->|VACÍO| Empty
    ClassifyIA -->|NO LISTA| NotReady
    ClassifyIA -->|LISTA| CorrectPos

    %% Los casos vacío y no lista van directo a MoreBelts
    Empty --> MoreBelts
    NotReady --> MoreBelts

    %% Proceso de cosecha en cadena horizontal
    CorrectPos --> Pick
    Pick --> Transport
    Transport --> MoveDeposit
    MoveDeposit --> Deposit
    Deposit --> ReturnArm
    ReturnArm --> MoreBelts

    %% Loop final
    MoreBelts -->|SÍ| LoopBelts
    MoreBelts -->|NO| ReturnOrigin --> End

    classDef startEnd fill:#2E7D32,stroke:#1B5E20,stroke-width:3px,color:#fff,font-weight:bold
    classDef process fill:#1565C0,stroke:#0D47A1,stroke-width:2px,color:#fff,font-weight:bold
    classDef decision fill:#D84315,stroke:#BF360C,stroke-width:2px,color:#fff,font-weight:bold
    classDef critical fill:#6A1B9A,stroke:#4A148C,stroke-width:2px,color:#fff,font-weight:bold
    classDef skip fill:#616161,stroke:#424242,stroke-width:2px,color:#fff
    classDef loop fill:#00838F,stroke:#006064,stroke-width:2px,color:#fff,font-weight:bold
"""

def generar_con_mermaid_cli():
    """Opción 1: Usar Mermaid CLI (mejor calidad)"""
    print("Generando diagrama con Mermaid CLI...")

    # Guardar código Mermaid en archivo temporal
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mmd_file = os.path.join(script_dir, 'imagenes', 'temp_diagrama.mmd')
    with open(mmd_file, 'w', encoding='utf-8') as f:
        f.write(mermaid_code)

    # Generar imagen con mmdc
    output_file = os.path.join(script_dir, 'imagenes', 'diagrama_flujo_cosecha.png')
    try:
        subprocess.run([
            'mmdc',
            '-i', mmd_file,
            '-o', output_file,
            '-w', '2000',   # PARÁMETRO: Ancho en píxeles (vertical pero ancho)
            '-H', '1400',   # PARÁMETRO: Alto en píxeles (compacto con nodos a los lados)
            '-b', 'white'   # Fondo blanco
        ], check=True)
        
        # Limpiar archivo temporal
        os.remove(mmd_file)
        
        print(f"OK - Diagrama generado exitosamente: {output_file}")
        print(f"\nNOTA: El tamano en LaTeX se controla con width= en el .tex")
        print(f"   Los parametros -w y -H controlan la RESOLUCION de la imagen")
        print(f"   Valores actuales: -w 2000 -H 1400 (vertical compacto con nodos laterales)")
        return True
        
    except FileNotFoundError:
        print("Error: mmdc no esta instalado.")
        print("   Instala con: npm install -g @mermaid-js/mermaid-cli")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error al generar diagrama: {e}")
        return False

def generar_con_playwright():
    """Opción 2: Usar Playwright (sin necesitar Node.js)"""
    print("Generando diagrama con Playwright...")

    try:
        from playwright.sync_api import sync_playwright

        # HTML con el diagrama Mermaid
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script type="module">
                import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                mermaid.initialize({{ startOnLoad: true, theme: 'base' }});
            </script>
            <style>
                body {{
                    margin: 0;
                    padding: 40px;
                    background: white;
                    display: flex;
                    justify-content: center;
                    align-items: flex-start;
                }}
                .mermaid {{
                    max-width: 100%;
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
            # PARÁMETROS DE TAMAÑO: width y height del viewport (ALTA RESOLUCIÓN para LaTeX)
            # Layout vertical compacto con nodos a los lados
            page = browser.new_page(viewport={'width': 4000, 'height': 2800}, device_scale_factor=2)
            page.set_content(html_content)

            # Esperar a que se renderice
            page.wait_for_timeout(3000)

            # Capturar screenshot solo del diagrama (sin espacio extra)
            diagram = page.locator('.mermaid svg')
            diagram.screenshot(
                path=output_file,
                type='png',
                omit_background=False
            )

            browser.close()

        print(f"OK - Diagrama generado exitosamente: {output_file}")
        print(f"\nNOTA: El tamano en LaTeX se controla con width= en el .tex")
        print(f"   Los parametros viewport controlan la RESOLUCION de la imagen")
        print(f"   Valores actuales: viewport 4000x2800 con device_scale_factor=2")
        print(f"   Resolucion efectiva: 8000x5600 pixels (vertical compacto con nodos laterales)")
        return True

    except ImportError:
        print("Error: playwright no esta instalado.")
        print("   Instala con: pip install playwright")
        print("   Luego ejecuta: playwright install chromium")
        return False
    except Exception as e:
        print(f"Error al generar diagrama: {e}")
        return False

def main():
    print("=" * 60)
    print("Generador de Diagrama de Flujo - Cosecha Interactiva")
    print("=" * 60)
    
    # Intentar primero con Mermaid CLI
    if generar_con_mermaid_cli():
        return
    
    print("\nIntentando método alternativo con Playwright...")
    if generar_con_playwright():
        return
    
    print("\n" + "=" * 60)
    print("No se pudo generar el diagrama. Por favor instala:")
    print("\nOPCIÓN 1 (Recomendada):")
    print("  npm install -g @mermaid-js/mermaid-cli")
    print("\nOPCIÓN 2 (Alternativa):")
    print("  pip install playwright")
    print("  playwright install chromium")
    print("=" * 60)

if __name__ == "__main__":
    main()