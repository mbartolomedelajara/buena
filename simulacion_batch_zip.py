import math
import json
import zipfile
import csv
from pathlib import Path
from cargar_datos import cargar_rutas, cargar_mapa
from contar_datos import contar_coches_todos_tiempos
from simulacion_ahorro import (
    CONFIGURACIONES, MU, SCS_HZ, T_SIMBOLO_S, T_SLOT_MS, PDB_MS, S, G, 
    BITRATE_BPS, SE, F_bits, generar_frame_bits, b_simbolo, b_slot, R,
    P_ACTIVA, P_ASM1, P_ASM2, P_ASM3, P_TRANS_ASM1, P_TRANS_ASM2, 
    P_TRANS_ASM3, SW_ASM1_SLOTS, SW_ASM2_SLOTS, SW_ASM3_SLOTS,
    calcular_consumo_instante, simular_configuracion
)

def mostrar_barra_progreso(actual, total, ancho=50):
    """Mostrar barra de progreso simple sin dependencias"""
    porcentaje = actual / total
    barra_llena = int(ancho * porcentaje)
    barra = '█' * barra_llena + '░' * (ancho - barra_llena)
    return f"[{barra}] {actual}/{total} ({porcentaje*100:.1f}%)"

def procesar_zip(ruta_zip, carpeta_salida="../resultados"):
    """
    Procesa todos los archivos JSON dentro de un ZIP
    y calcula la MEDIA de resultados de simulacion_ahorro.
    
    :param ruta_zip: Ruta al archivo ZIP
    :param carpeta_salida: Carpeta donde guardar resultados
    """
    # Crear carpeta de salida si no existe
    Path(carpeta_salida).mkdir(parents=True, exist_ok=True)
    
    # Acumuladores para promedios
    acumuladores = {
        "A": {"consumo": 0, "baseline": 0, "ahorro": 0, "instantes": 0, "count": 0},
        "B": {"consumo": 0, "baseline": 0, "ahorro": 0, "instantes": 0, "count": 0},
        "C": {"consumo": 0, "baseline": 0, "ahorro": 0, "instantes": 0, "count": 0},
        "D": {"consumo": 0, "baseline": 0, "ahorro": 0, "instantes": 0, "count": 0},
    }
    
    print(f"\nAbriendo ZIP: {ruta_zip}")
    print("=" * 80)
    
    with zipfile.ZipFile(ruta_zip, 'r') as zf:
        # Encontrar todos los archivos .json
        archivos_rutas = [f for f in zf.namelist() if f.endswith('.json')]
        
        print(f"Encontrados {len(archivos_rutas)} archivos JSON")
        print("Procesando simulaciones...")
        print("=" * 80)
        
        errores = 0
        
        for idx, ruta_archivo in enumerate(archivos_rutas, 1):
            print(f"\r{mostrar_barra_progreso(idx, len(archivos_rutas))}", end=" | ", flush=True)
            print(f"📄 {Path(ruta_archivo).name[:50]}", end="\n")
            
            try:
                # Cargar datos desde ZIP
                rutas = cargar_rutas(ruta_archivo, zip_file=zf)
                
                # Calcular grid de tiempo
                T_max = max(
                    car["times"][-1][1]
                    for car_id, car in rutas.items()
                    if car_id.isdigit() and car.get("times")
                )
                time_grid = list(range(0, int(T_max) + 2))
                
                # Contar coches
                resultados_tiempos = contar_coches_todos_tiempos(rutas, time_grid)
                
                # Simular configuraciones
                config_baseline = CONFIGURACIONES["D"]
                
                for nombre, config in CONFIGURACIONES.items():
                    datos = simular_configuracion(
                        resultados_tiempos, config, config_baseline
                    )
                    
                    if "error" not in datos:
                        acumuladores[nombre]["consumo"] += datos.get("consumo_total", 0)
                        acumuladores[nombre]["baseline"] += datos.get("baseline_total", 0)
                        acumuladores[nombre]["ahorro"] += datos.get("ahorro_porcentaje", 0)
                        acumuladores[nombre]["instantes"] += datos.get("instantes_evaluados", 0)
                        acumuladores[nombre]["count"] += 1
                
            except Exception as e:
                errores += 1
                continue
    
    # Calcular promedios
    print("\n" + "=" * 80)
    print("RESULTADOS PROMEDIADOS")
    print("=" * 80)
    
    resultados_finales = []
    
    for config_name in ["A", "B", "C", "D"]:
        acc = acumuladores[config_name]
        if acc["count"] > 0:
            media_ahorro = acc["ahorro"] / acc["count"]
            media_consumo = acc["consumo"] / acc["count"]
            media_baseline = acc["baseline"] / acc["count"]
            media_instantes = acc["instantes"] / acc["count"]
            
            desc = CONFIGURACIONES[config_name]["descripcion"]
            print(f"\nConfig {config_name}: {desc}")
            print(f"  Simulaciones:         {acc['count']}")
            print(f"  Ahorro medio:         {media_ahorro:.2f}%")
            print(f"  Consumo medio:        {media_consumo:.6f}")
            print(f"  Baseline medio:       {media_baseline:.6f}")
            
            resultados_finales.append({
                "config": config_name,
                "descripcion": desc,
                "ahorro_medio_porcentaje": round(media_ahorro, 2),
                "consumo_medio": round(media_consumo, 6),
                "baseline_medio": round(media_baseline, 6),
                "simulaciones_exitosas": acc["count"],
                "total_archivos": len(archivos_rutas)
            })
    
    # Guardar resultado consolidado en CSV
    if resultados_finales:
        csv_file = Path(carpeta_salida) / "resultado_promedio.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=resultados_finales[0].keys())
            writer.writeheader()
            writer.writerows(resultados_finales)
        
        # También guardar en JSON
        json_file = Path(carpeta_salida) / "resultado_promedio.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(resultados_finales, f, indent=2)
        
        print(f"\n{'=' * 80}")
        print(f"✓ Resultados guardados en:")
        print(f"  📊 CSV:  {csv_file}")
        print(f"  📋 JSON: {json_file}")
        print(f"{'=' * 80}\n")
    
    if errores > 0:
        print(f"⚠ {errores} archivos con errores")
    
    return resultados_finales


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python simulacion_batch_zip.py <ruta_zip> [carpeta_salida]")
        print("\nEjemplo:")
        print("  python simulacion_batch_zip.py datos.zip ../resultados")
        sys.exit(1)
    
    ruta_zip = sys.argv[1]
    carpeta_salida = sys.argv[2] if len(sys.argv) > 2 else "../resultados"
    
    procesar_zip(ruta_zip, carpeta_salida)
