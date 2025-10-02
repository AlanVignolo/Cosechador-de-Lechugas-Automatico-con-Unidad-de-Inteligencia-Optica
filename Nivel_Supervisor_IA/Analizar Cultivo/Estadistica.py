"""
ANÁLISIS ESTADÍSTICO DE GRUPOS
Script que procesa 3 carpetas (lechugas, plantines, vasos) y genera estadísticas comparativas
"""

import cv2
import numpy as np
from pathlib import Path
import json
import matplotlib.pyplot as plt
from scipy import stats as scipy_stats
import sys

# ============================================================================
# PASO 1: IMPORTAR EL DETECTOR DEL ARCHIVO ANTERIOR
# ============================================================================
# Asegúrate de que el archivo del detector esté en la misma carpeta
# o ajusta el import según tu estructura

# Si el detector está en "ContornoEstadisticas.py":
# from ContornoEstadisticas import EdgeDetectorOptimized

# Si está en otro archivo, ajusta:
# sys.path.append('/ruta/al/archivo')
# from nombre_archivo import EdgeDetectorOptimized


class GroupStatisticsAnalyzer:
    """Analizador estadístico que procesa múltiples grupos y compara"""
    
    def __init__(self):
        self.group_data = {}
        
    def analyze_folder(self, folder_path, group_name, detector):
        """Analiza todas las imágenes de una carpeta"""
        print(f"\n{'='*70}")
        print(f"ANALIZANDO GRUPO: {group_name}")
        print(f"Carpeta: {folder_path}")
        print(f"{'='*70}")
        
        folder = Path(folder_path)
        if not folder.exists():
            print(f"❌ ERROR: La carpeta no existe: {folder_path}")
            return
        
        # Buscar imágenes
        image_files = []
        for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
            image_files.extend(folder.glob(f'*{ext}'))
            image_files.extend(folder.glob(f'*{ext.upper()}'))
        
        if not image_files:
            print(f"⚠ No se encontraron imágenes en {folder_path}")
            return
        
        print(f"Imágenes encontradas: {len(image_files)}")
        
        # Almacenar datos de todos los contornos del grupo
        green_pixels_list = []
        black_pixels_list = []
        total_pixels_list = []
        green_ratio_list = []
        black_ratio_list = []
        areas_list = []
        
        images_processed = 0
        
        for img_path in image_files:
            print(f"  Procesando: {img_path.name}...", end=" ")
            
            image = cv2.imread(str(img_path))
            if image is None:
                print("ERROR al leer")
                continue
            
            # Limpiar pasos previos
            detector.steps = {}
            
            try:
                # Ejecutar detección
                binary, contours = detector.detect_edges(image)
                
                # IMPORTANTE: Verificar que el detector tenga el atributo
                if not hasattr(detector, 'last_contour_stats'):
                    print("⚠ ADVERTENCIA: El detector no tiene 'last_contour_stats'")
                    print("   Verifica que EdgeDetectorOptimized.analyze_contours_statistics()")
                    print("   incluya la línea: self.last_contour_stats = stats_list")
                    continue
                
                # Extraer estadísticas guardadas
                if detector.last_contour_stats and len(detector.last_contour_stats) > 0:
                    for stats in detector.last_contour_stats:
                        green_pixels_list.append(stats['green_pixels'])
                        black_pixels_list.append(stats['black_pixels'])
                        total_pixels_list.append(stats['green_pixels'] + stats['black_pixels'])
                        green_ratio_list.append(stats['green_ratio'])
                        black_ratio_list.append(stats['black_ratio'])
                        areas_list.append(stats['area'])
                    
                    print(f"OK ({len(detector.last_contour_stats)} contornos)")
                    images_processed += 1
                else:
                    print("⚠ Sin contornos detectados")
            
            except Exception as e:
                print(f"ERROR: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Calcular estadísticas del grupo
        if len(green_pixels_list) > 0:
            self.group_data[group_name] = {
                'n_contours': len(green_pixels_list),
                'n_images': images_processed,
                'green_pixels': {
                    'mean': np.mean(green_pixels_list),
                    'std': np.std(green_pixels_list),
                    'min': np.min(green_pixels_list),
                    'max': np.max(green_pixels_list),
                    'median': np.median(green_pixels_list),
                    'data': green_pixels_list
                },
                'black_pixels': {
                    'mean': np.mean(black_pixels_list),
                    'std': np.std(black_pixels_list),
                    'min': np.min(black_pixels_list),
                    'max': np.max(black_pixels_list),
                    'median': np.median(black_pixels_list),
                    'data': black_pixels_list
                },
                'total_pixels': {
                    'mean': np.mean(total_pixels_list),
                    'std': np.std(total_pixels_list),
                    'min': np.min(total_pixels_list),
                    'max': np.max(total_pixels_list),
                    'median': np.median(total_pixels_list),
                    'data': total_pixels_list
                },
                'green_ratio': {
                    'mean': np.mean(green_ratio_list),
                    'std': np.std(green_ratio_list),
                    'data': green_ratio_list
                },
                'black_ratio': {
                    'mean': np.mean(black_ratio_list),
                    'std': np.std(black_ratio_list),
                    'data': black_ratio_list
                },
                'areas': {
                    'mean': np.mean(areas_list),
                    'std': np.std(areas_list),
                    'data': areas_list
                }
            }
            
            print(f"\n✓ Grupo '{group_name}' procesado:")
            print(f"  - {images_processed} imágenes procesadas")
            print(f"  - {len(green_pixels_list)} contornos detectados")
            print(f"  - Promedio píxeles verdes: {np.mean(green_pixels_list):.0f}")
            print(f"  - Promedio píxeles negros: {np.mean(black_pixels_list):.0f}")
            print(f"  - Promedio total: {np.mean(total_pixels_list):.0f}")
        else:
            print(f"\n⚠ No se detectaron contornos en grupo '{group_name}'")
    
    def calculate_separability(self):
        """Calcula métricas de separabilidad entre grupos"""
        print(f"\n{'='*70}")
        print("ANÁLISIS DE SEPARABILIDAD ENTRE GRUPOS")
        print(f"{'='*70}\n")
        
        groups = list(self.group_data.keys())
        if len(groups) < 2:
            print("⚠ Se necesitan al menos 2 grupos para calcular separabilidad")
            return {}
        
        metrics = ['green_pixels', 'black_pixels', 'total_pixels']
        separability_results = {}
        
        for metric in metrics:
            print(f"\n{'─'*70}")
            print(f"MÉTRICA: {metric.upper().replace('_', ' ')}")
            print(f"{'─'*70}")
            
            separability_results[metric] = {}
            
            for i, group1 in enumerate(groups):
                for group2 in groups[i+1:]:
                    data1 = np.array(self.group_data[group1][metric]['data'])
                    data2 = np.array(self.group_data[group2][metric]['data'])
                    
                    # Test t de Student
                    t_stat, p_value = scipy_stats.ttest_ind(data1, data2)
                    
                    # Tamaño del efecto (Cohen's d)
                    mean1 = np.mean(data1)
                    mean2 = np.mean(data2)
                    std1 = np.std(data1, ddof=1)
                    std2 = np.std(data2, ddof=1)
                    
                    n1, n2 = len(data1), len(data2)
                    pooled_std = np.sqrt(((n1-1)*std1**2 + (n2-1)*std2**2) / (n1+n2-2))
                    cohens_d = (mean1 - mean2) / pooled_std if pooled_std > 0 else 0
                    
                    # Interpretación
                    if abs(cohens_d) < 0.2:
                        effect_size = "TRIVIAL"
                        emoji = "❌"
                    elif abs(cohens_d) < 0.5:
                        effect_size = "PEQUEÑO"
                        emoji = "⚠️"
                    elif abs(cohens_d) < 0.8:
                        effect_size = "MEDIANO"
                        emoji = "✓"
                    else:
                        effect_size = "GRANDE"
                        emoji = "✓✓"
                    
                    # Evaluación final
                    well_separated = (abs(cohens_d) > 0.8 and p_value < 0.05)
                    
                    pair = f"{group1} vs {group2}"
                    separability_results[metric][pair] = {
                        't_statistic': float(t_stat),
                        'p_value': float(p_value),
                        'cohens_d': float(cohens_d),
                        'effect_size': effect_size,
                        'significant': p_value < 0.05,
                        'well_separated': well_separated,
                        'mean1': float(mean1),
                        'mean2': float(mean2),
                        'std1': float(std1),
                        'std2': float(std2)
                    }
                    
                    print(f"\n{pair}:")
                    print(f"  Media Grupo 1: {mean1:.1f} ± {std1:.1f}")
                    print(f"  Media Grupo 2: {mean2:.1f} ± {std2:.1f}")
                    print(f"  Diferencia absoluta: {abs(mean1 - mean2):.1f}")
                    print(f"  p-value: {p_value:.6f} {'(significativo ✓)' if p_value < 0.05 else '(NO significativo ❌)'}")
                    print(f"  Cohen's d: {cohens_d:.3f} (efecto {effect_size})")
                    print(f"  {emoji} Separabilidad: {'BIEN DIFERENCIADOS' if well_separated else 'POCO DIFERENCIADOS'}")
        
        return separability_results
    
    def generate_report(self, output_folder):
        """Genera informe completo"""
        output_path = Path(output_folder)
        output_path.mkdir(parents=True, exist_ok=True)
        
        print(f"\n{'='*70}")
        print("GENERANDO INFORME ESTADÍSTICO")
        print(f"{'='*70}\n")
        
        # 1. Calcular separabilidad
        separability = self.calculate_separability()
        
        # 2. Tabla resumen
        self.create_summary_table(output_path)
        
        # 3. Tabla de separabilidad
        self.create_separability_table(output_path, separability)
        
        # 4. Gráficos
        self.create_all_plots(output_path)
        
        # 5. JSON
        self.export_json(output_path, separability)
        
        print(f"\n{'='*70}")
        print(f"✓ INFORME COMPLETO GENERADO EN: {output_path}")
        print(f"{'='*70}\n")
        print("Archivos generados:")
        print("  📄 resumen_estadistico.txt - Tabla con todas las métricas")
        print("  📄 separabilidad.txt - Análisis de diferenciación entre grupos")
        print("  📊 comparacion_medias.png - Gráfico de barras")
        print("  📊 boxplots.png - Diagramas de caja")
        print("  📊 distribuciones.png - Histogramas")
        print("  💾 estadisticas_completas.json - Datos completos")
    
    def create_summary_table(self, output_path):
        """Tabla resumen en texto"""
        txt_path = output_path / "resumen_estadistico.txt"
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("╔" + "═"*78 + "╗\n")
            f.write("║" + " "*20 + "RESUMEN ESTADÍSTICO POR GRUPO" + " "*29 + "║\n")
            f.write("╚" + "═"*78 + "╝\n\n")
            
            for group_name, data in self.group_data.items():
                f.write(f"\n{'─'*80}\n")
                f.write(f"GRUPO: {group_name}\n")
                f.write(f"{'─'*80}\n")
                f.write(f"Imágenes procesadas: {data['n_images']}\n")
                f.write(f"Contornos detectados: {data['n_contours']}\n")
                f.write(f"Promedio contornos/imagen: {data['n_contours']/data['n_images']:.1f}\n\n")
                
                # Verde
                cv_green = (data['green_pixels']['std']/data['green_pixels']['mean']*100 
                           if data['green_pixels']['mean'] > 0 else 0)
                f.write(f"PÍXELES VERDES:\n")
                f.write(f"  Media:    {data['green_pixels']['mean']:>10.2f}\n")
                f.write(f"  Desv.Est: {data['green_pixels']['std']:>10.2f}\n")
                f.write(f"  Mediana:  {data['green_pixels']['median']:>10.2f}\n")
                f.write(f"  Rango:    [{data['green_pixels']['min']:.0f} - {data['green_pixels']['max']:.0f}]\n")
                f.write(f"  Coef.Var: {cv_green:>10.1f}%\n\n")
                
                # Negro
                cv_black = (data['black_pixels']['std']/data['black_pixels']['mean']*100 
                           if data['black_pixels']['mean'] > 0 else 0)
                f.write(f"PÍXELES NEGROS:\n")
                f.write(f"  Media:    {data['black_pixels']['mean']:>10.2f}\n")
                f.write(f"  Desv.Est: {data['black_pixels']['std']:>10.2f}\n")
                f.write(f"  Mediana:  {data['black_pixels']['median']:>10.2f}\n")
                f.write(f"  Rango:    [{data['black_pixels']['min']:.0f} - {data['black_pixels']['max']:.0f}]\n")
                f.write(f"  Coef.Var: {cv_black:>10.1f}%\n\n")
                
                # Total
                cv_total = (data['total_pixels']['std']/data['total_pixels']['mean']*100)
                f.write(f"TOTAL (VERDE + NEGRO):\n")
                f.write(f"  Media:    {data['total_pixels']['mean']:>10.2f}\n")
                f.write(f"  Desv.Est: {data['total_pixels']['std']:>10.2f}\n")
                f.write(f"  Mediana:  {data['total_pixels']['median']:>10.2f}\n")
                f.write(f"  Rango:    [{data['total_pixels']['min']:.0f} - {data['total_pixels']['max']:.0f}]\n")
                f.write(f"  Coef.Var: {cv_total:>10.1f}%\n\n")
                
                # Ratios
                f.write(f"RATIOS PROMEDIO:\n")
                f.write(f"  Verde: {data['green_ratio']['mean']:>6.1%}\n")
                f.write(f"  Negro: {data['black_ratio']['mean']:>6.1%}\n")
        
        print(f"  ✓ {txt_path.name}")
    
    def create_separability_table(self, output_path, separability):
        """Tabla de separabilidad"""
        txt_path = output_path / "separabilidad.txt"
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("╔" + "═"*78 + "╗\n")
            f.write("║" + " "*18 + "ANÁLISIS DE SEPARABILIDAD ENTRE GRUPOS" + " "*22 + "║\n")
            f.write("╚" + "═"*78 + "╝\n\n")
            
            for metric, pairs in separability.items():
                f.write(f"\n{'═'*80}\n")
                f.write(f"MÉTRICA: {metric.upper().replace('_', ' ')}\n")
                f.write(f"{'═'*80}\n")
                
                for pair, stats in pairs.items():
                    f.write(f"\n{pair}:\n")
                    f.write(f"  Media 1: {stats['mean1']:.1f} ± {stats['std1']:.1f}\n")
                    f.write(f"  Media 2: {stats['mean2']:.1f} ± {stats['std2']:.1f}\n")
                    f.write(f"  Diferencia: {abs(stats['mean1'] - stats['mean2']):.1f}\n")
                    f.write(f"  p-value: {stats['p_value']:.6f} ")
                    f.write(f"{'✓ SIGNIFICATIVO' if stats['significant'] else '✗ NO SIGNIFICATIVO'}\n")
                    f.write(f"  Cohen's d: {stats['cohens_d']:.3f} ({stats['effect_size']})\n")
                    f.write(f"  EVALUACIÓN: ")
                    if stats['well_separated']:
                        f.write("✓✓ BIEN DIFERENCIADOS\n")
                    else:
                        f.write("⚠ POCO DIFERENCIADOS\n")
        
        print(f"  ✓ {txt_path.name}")
    
    def create_all_plots(self, output_path):
        """Crea todos los gráficos"""
        if not self.group_data:
            print("⚠ No hay datos para generar gráficos")
            return
        
        metrics = ['green_pixels', 'black_pixels', 'total_pixels']
        groups = list(self.group_data.keys())
        
        if len(groups) == 0:
            print("⚠ No hay grupos para graficar")
            return
        
        # Gráfico 1: Barras con medias
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        fig.suptitle('Comparación de Medias por Grupo', fontsize=16, fontweight='bold')
        
        colors = ['green', 'gray', 'blue', 'orange', 'purple']
        
        for idx, metric in enumerate(metrics):
            ax = axes[idx]
            means = [self.group_data[g][metric]['mean'] for g in groups]
            stds = [self.group_data[g][metric]['std'] for g in groups]
            
            x_pos = np.arange(len(groups))
            bars = ax.bar(x_pos, means, yerr=stds, capsize=10, alpha=0.7, 
                         color=colors[:len(groups)])
            
            ax.set_xticks(x_pos)
            ax.set_xticklabels(groups, rotation=45, ha='right')
            ax.set_ylabel('Píxeles', fontsize=11)
            ax.set_title(metric.replace('_', ' ').title(), fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
            
            for i, (m, s) in enumerate(zip(means, stds)):
                ax.text(i, m + s + max(means)*0.05, f'{m:.0f}±{s:.0f}', 
                       ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(output_path / "comparacion_medias.png", dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ comparacion_medias.png")
        
        # Gráfico 2: Boxplots
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        fig.suptitle('Distribución por Grupo (Boxplots)', fontsize=16, fontweight='bold')
        
        for idx, metric in enumerate(metrics):
            ax = axes[idx]
            
            # Preparar datos para boxplot
            data_to_plot = []
            labels_to_plot = []
            
            for g in groups:
                if metric in self.group_data[g] and 'data' in self.group_data[g][metric]:
                    data = self.group_data[g][metric]['data']
                    if len(data) > 0:
                        data_to_plot.append(data)
                        labels_to_plot.append(g)
            
            if len(data_to_plot) > 0:
                # Usar tick_labels en lugar de labels (Matplotlib 3.9+)
                bp = ax.boxplot(data_to_plot, tick_labels=labels_to_plot, patch_artist=True,
                               medianprops=dict(color='red', linewidth=2))
                
                boxcolors = ['lightgreen', 'lightgray', 'lightblue', 'lightyellow', 'lightpink']
                for patch, color in zip(bp['boxes'], boxcolors[:len(data_to_plot)]):
                    patch.set_facecolor(color)
                
                ax.set_xticklabels(labels_to_plot, rotation=45, ha='right')
            
            ax.set_ylabel('Píxeles', fontsize=11)
            ax.set_title(metric.replace('_', ' ').title(), fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        plt.savefig(output_path / "boxplots.png", dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ boxplots.png")
        
        # Gráfico 3: Histogramas
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        fig.suptitle('Distribuciones por Grupo', fontsize=16, fontweight='bold')
        
        for idx, metric in enumerate(metrics):
            ax = axes[idx]
            
            for group in groups:
                if metric in self.group_data[group] and 'data' in self.group_data[group][metric]:
                    data = self.group_data[group][metric]['data']
                    if len(data) > 0:
                        ax.hist(data, alpha=0.5, label=group, bins=20, edgecolor='black')
            
            ax.set_xlabel('Píxeles', fontsize=11)
            ax.set_ylabel('Frecuencia', fontsize=11)
            ax.set_title(metric.replace('_', ' ').title(), fontsize=12, fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path / "distribuciones.png", dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ distribuciones.png")
    
    def export_json(self, output_path, separability):
        """Exporta JSON completo"""
        json_path = output_path / "estadisticas_completas.json"
        
        # Convertir separabilidad a formato serializable
        separability_serializable = {}
        for metric, pairs in separability.items():
            separability_serializable[metric] = {}
            for pair, stats in pairs.items():
                separability_serializable[metric][pair] = {
                    't_statistic': float(stats['t_statistic']),
                    'p_value': float(stats['p_value']),
                    'cohens_d': float(stats['cohens_d']),
                    'effect_size': str(stats['effect_size']),
                    'significant': bool(stats['significant']),  # Convertir explícitamente
                    'well_separated': bool(stats['well_separated']),  # Convertir explícitamente
                    'mean1': float(stats['mean1']),
                    'mean2': float(stats['mean2']),
                    'std1': float(stats['std1']),
                    'std2': float(stats['std2'])
                }
        
        export_data = {
            'grupos': {},
            'separabilidad': separability_serializable
        }
        
        for group_name, data in self.group_data.items():
            export_data['grupos'][group_name] = {
                'n_contours': int(data['n_contours']),
                'n_images': int(data['n_images']),
                'green_pixels': {
                    'mean': float(data['green_pixels']['mean']),
                    'std': float(data['green_pixels']['std']),
                    'median': float(data['green_pixels']['median']),
                    'min': float(data['green_pixels']['min']),
                    'max': float(data['green_pixels']['max'])
                },
                'black_pixels': {
                    'mean': float(data['black_pixels']['mean']),
                    'std': float(data['black_pixels']['std']),
                    'median': float(data['black_pixels']['median']),
                    'min': float(data['black_pixels']['min']),
                    'max': float(data['black_pixels']['max'])
                },
                'total_pixels': {
                    'mean': float(data['total_pixels']['mean']),
                    'std': float(data['total_pixels']['std']),
                    'median': float(data['total_pixels']['median']),
                    'min': float(data['total_pixels']['min']),
                    'max': float(data['total_pixels']['max'])
                }
            }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ {json_path.name}")


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    """Función principal de análisis"""
    
    print("\n" + "╔" + "═"*68 + "╗")
    print("║" + " "*10 + "ANÁLISIS ESTADÍSTICO DE GRUPOS - LECHUGAS/PLANTINES/VASOS" + " "*1 + "║")
    print("╚" + "═"*68 + "╝\n")
    
    # ==================== CONFIGURACIÓN ====================
    # IMPORTANTE: Ajusta estas rutas según tu estructura
    
    # Opción 1: Si el detector está en el mismo archivo
    # (copia la clase EdgeDetectorOptimized aquí)
    
    # Opción 2: Si el detector está en otro archivo
    # Descomenta y ajusta:
    # from ContornoEstadisticas import EdgeDetectorOptimized
    
    FOLDERS = {
        'LECHUGAS': '/home/brenda/Documents/BD_ORIGINALES/recortadas/lechugas',
        'PLANTINES': '/home/brenda/Documents/BD_ORIGINALES/recortadas/plantines',
        'VASOS': '/home/brenda/Documents/BD_ORIGINALES/recortadas/vasos'
    }
    
    OUTPUT_FOLDER = '/home/brenda/Documents/validation/estadisticas_grupos'
    # =======================================================
    
    print("Configuración:")
    print("─" * 70)
    for name, path in FOLDERS.items():
        exists = "✓" if Path(path).exists() else "✗"
        print(f"  {exists} {name:12s}: {path}")
    print(f"  → Salida:     {OUTPUT_FOLDER}\n")
    
    # Verificar carpetas
    missing = [name for name, path in FOLDERS.items() if not Path(path).exists()]
    if missing:
        print(f"❌ ERROR: Faltan carpetas: {', '.join(missing)}")
        print("   Ajusta las rutas en FOLDERS y vuelve a ejecutar")
        return
    
    # Importar detector
    try:
        # AJUSTA ESTE IMPORT SEGÚN TU ARCHIVO
        from ContornosBIenFIltrados import EdgeDetectorOptimized
        print("✓ Detector importado correctamente\n")
    except ImportError as e:
        print(f"❌ ERROR: No se pudo importar EdgeDetectorOptimized")
        print(f"   {e}")
        print("   Ajusta el import en la línea 558")
        return
    
    # Ejecutar análisis
    print("Iniciando análisis...\n")
    
    detector = EdgeDetectorOptimized()
    analyzer = GroupStatisticsAnalyzer()
    
    # Procesar cada carpeta
    for group_name, folder_path in FOLDERS.items():
        analyzer.analyze_folder(folder_path, group_name, detector)
    
    # Generar informe
    analyzer.generate_report(OUTPUT_FOLDER)
    
    print("\n✓ ANÁLISIS COMPLETADO\n")


if __name__ == "__main__":
    main()