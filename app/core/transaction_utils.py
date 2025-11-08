from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

@asynccontextmanager
async def transaction_manager(db: AsyncSession):
    """Gestionnaire de contexte pour les transactions de base de données.
    
    Args:
        db (AsyncSession): Session de base de données
        
    Usage:
        async with transaction_manager(db) as session:
            # Votre code ici
            # La transaction sera automatiquement commitée si tout se passe bien
            # ou rollbackée en cas d'erreur
    """
    print("\n=== 🔄 DÉBUT TRANSACTION ===")
    try:
        if not db.is_active:
            print("🔄 Démarrage d'une nouvelle transaction")
            await db.begin()
        yield db
        if db.is_active:
            print("✅ Commit de la transaction")
            await db.commit()
            print("✅ Transaction commitée avec succès")
    except Exception as e:
        print(f"❌ Erreur dans la transaction: {str(e)}")
        if db.is_active:
            print("🔄 Rollback de la transaction")
            await db.rollback()
            print("🔄 Transaction rollback effectué")
        raise
    finally:
        print("=== FIN TRANSACTION ===\n") 