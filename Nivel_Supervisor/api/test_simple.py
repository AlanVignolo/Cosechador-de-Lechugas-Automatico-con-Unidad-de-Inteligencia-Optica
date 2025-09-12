#!/usr/bin/env python3
"""
Test simple para verificar que las dependencias funcionan
"""

def test_imports():
    """Probar imports básicos"""
    try:
        print("🧪 Probando imports...")
        
        print("   - sqlite3...", end="")
        import sqlite3
        print(" OK")
        
        print("   - fastapi...", end="")
        import fastapi
        print(f" OK (v{fastapi.__version__})")
        
        print("   - uvicorn...", end="")
        import uvicorn
        print(f" OK")
        
        print("   - sqlalchemy...", end="")
        import sqlalchemy
        print(f" OK (v{sqlalchemy.__version__})")
        
        print("   - pydantic...", end="")
        import pydantic
        print(f" OK (v{pydantic.VERSION})")
        
        print("\nTodos los imports funcionan correctamente!")
        return True
        
    except ImportError as e:
        print(f"\nError importing: {e}")
        return False

def test_database():
    """Probar conexión básica a SQLite"""
    try:
        print("\n🗄️  Probando SQLite...")
        import sqlite3
        
        # Crear conexión temporal
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        
        # Crear tabla de prueba
        cursor.execute('''
            CREATE TABLE test (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        ''')
        
        # Insertar datos
        cursor.execute("INSERT INTO test (name) VALUES (?)", ("CLAUDIO",))
        conn.commit()
        
        # Leer datos
        cursor.execute("SELECT * FROM test")
        result = cursor.fetchone()
        
        conn.close()
        
        if result and result[1] == "CLAUDIO":
            print("SQLite funciona correctamente!")
            return True
        else:
            print("Error en SQLite")
            return False
            
    except Exception as e:
        print(f"Error en SQLite: {e}")
        return False

def test_basic_api():
    """Probar creación básica de API"""
    try:
        print("\n🌐 Probando FastAPI básico...")
        from fastapi import FastAPI
        
        app = FastAPI(title="Test CLAUDIO API")
        
        @app.get("/")
        def root():
            return {"message": "CLAUDIO Test API funciona!"}
        
        print("FastAPI básico funciona correctamente!")
        return True
        
    except Exception as e:
        print(f"Error en FastAPI: {e}")
        return False

if __name__ == "__main__":
    print("CLAUDIO - Test de Dependencias")
    print("=" * 40)
    
    success = True
    
    success &= test_imports()
    success &= test_database()
    success &= test_basic_api()
    
    print("\n" + "=" * 40)
    if success:
        print("¡Todo funciona! Puedes ejecutar:")
        print("   python init_database.py")
        print("   python main.py")
    else:
        print("Hay problemas. Verifica las dependencias.")
    
    print("=" * 40)