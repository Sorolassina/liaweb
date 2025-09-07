from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
import traceback

async def diagnose_sequence(db: AsyncSession, table_name: str, id_column: str = "id") -> dict:
    """
    Diagnostique l'état d'une séquence PostgreSQL.
    
    Args:
        db: Session de base de données
        table_name: Nom de la table
        id_column: Nom de la colonne ID (par défaut: "id")
    
    Returns:
        dict: Informations sur l'état de la séquence
    """
    print(f"\n=== 🔍 DIAGNOSTIC DE LA SÉQUENCE {table_name}_{id_column}_seq ===")
    try:
        # Vérifier le dernier ID utilisé
        result = await db.execute(
            select(func.max(text(id_column))).select_from(text(table_name))
        )
        max_id = result.scalar_one() or 0
        print(f"📊 Dernier ID utilisé dans la table: {max_id}")
        
        # Vérifier la valeur actuelle de la séquence
        result = await db.execute(
            text(f"SELECT last_value, is_called FROM {table_name}_{id_column}_seq")
        )
        seq_info = result.fetchone()
        print(f"📊 État de la séquence:")
        print(f"  - Dernière valeur: {seq_info[0]}")
        print(f"  - Séquence appelée: {seq_info[1]}")
        
        # Vérifier s'il y a des trous dans la séquence en utilisant une sous-requête
        result = await db.execute(
            text(f"""
                WITH ordered_ids AS (
                    SELECT {id_column},
                           LAG({id_column}) OVER (ORDER BY {id_column}) as prev_id
                    FROM {table_name}
                    WHERE {id_column} > 1
                )
                SELECT {id_column}, prev_id
                FROM ordered_ids
                WHERE {id_column} - prev_id > 1
            """)
        )
        gaps = result.fetchall()
        if gaps:
            print("\n⚠️ Trous détectés dans la séquence:")
            for gap in gaps:
                print(f"  - Trou entre {gap[1]} et {gap[0]}")
        else:
            print("\n✅ Aucun trou détecté dans la séquence")
        
        # Préparer le résultat
        diagnosis = {
            "max_id": max_id,
            "sequence_last_value": seq_info[0],
            "sequence_is_called": seq_info[1],
            "gaps": [(gap[1], gap[0]) for gap in gaps] if gaps else [],
            "is_healthy": max_id == seq_info[0] and not gaps
        }
        
        print("\n=== FIN DIAGNOSTIC ===\n")
        return diagnosis
        
    except Exception as e:
        print(f"❌ Erreur lors du diagnostic: {str(e)}")
        print(f"📋 Traceback:\n{traceback.format_exc()}")
        raise

async def reset_sequence(db: AsyncSession, table_name: str, id_column: str = "id") -> None:
    """
    Réinitialise une séquence PostgreSQL à la valeur maximale + 1.
    
    Args:
        db: Session de base de données
        table_name: Nom de la table
        id_column: Nom de la colonne ID (par défaut: "id")
    """
    print(f"\n=== 🔄 RÉINITIALISATION DE LA SÉQUENCE {table_name}_{id_column}_seq ===")
    try:
        # Récupérer le plus grand ID existant
        result = await db.execute(
            select(func.max(text(id_column))).select_from(text(table_name))
        )
        max_id = result.scalar_one() or 0
        print(f"📊 ID maximum actuel: {max_id}")
        
        # Réinitialiser la séquence
        await db.execute(
            text(f"ALTER SEQUENCE {table_name}_{id_column}_seq RESTART WITH {max_id + 1}")
        )
        print(f"✅ Séquence réinitialisée à {max_id + 1}")
        
        # Commit des changements
        await db.commit()
        print("=== FIN RÉINITIALISATION DE LA SÉQUENCE ===\n")
        
    except Exception as e:
        print(f"❌ Erreur lors de la réinitialisation: {str(e)}")
        print(f"📋 Traceback:\n{traceback.format_exc()}")
        raise 