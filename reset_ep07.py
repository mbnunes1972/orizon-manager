"""
reset_ep07.py — Limpa tabelas EP-07 sem tocar em dados existentes.
Uso: python reset_ep07.py
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orizon.db")

TABELAS_EP07    = ["orcamento_ambientes", "orcamentos", "pool_ambientes"]
TABELAS_INTACTAS = ["usuarios", "sessoes", "log_autorizacoes", "clientes", "parceiros"]

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

print("=== ANTES ===")
for t in TABELAS_EP07 + TABELAS_INTACTAS:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    print(f"  {t:<25} {cur.fetchone()[0]} registros")

print("\nDeletando tabelas EP-07...")
# Ordem importa: FK orcamento_ambientes → orcamentos e pool_ambientes
for t in TABELAS_EP07:
    cur.execute(f"DELETE FROM {t}")
    print(f"  {t} — deletado")

conn.commit()

print("\n=== DEPOIS ===")
for t in TABELAS_EP07 + TABELAS_INTACTAS:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    n = cur.fetchone()[0]
    status = "OK (zerado)" if t in TABELAS_EP07 else "OK (intocado)"
    print(f"  {t:<25} {n} registros  — {status}")

conn.close()
print("\nConcluído.")
