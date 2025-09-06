# app/services/ACD/permissions.py
from typing import List, Optional, Set, Dict
from sqlmodel import Session, select
from datetime import datetime, timezone

from ...models.enums import UserRole
from ...models.ACD.permissions import (
    PermissionRole, PermissionUtilisateur, LogPermission,
    NiveauPermission, TypeRessource
)
from ...models.base import User

class PermissionService:
    """Service de gestion des permissions"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_user_permissions(self, user: User) -> Dict[TypeRessource, NiveauPermission]:
        """Récupère toutes les permissions d'un utilisateur"""
        permissions = {}
        
        # Permissions par rôle
        role_permissions = self.session.exec(
            select(PermissionRole).where(PermissionRole.role == user.role)
        ).all()
        
        for perm in role_permissions:
            permissions[perm.ressource] = perm.niveau_permission
        
        # Permissions spécifiques à l'utilisateur (surcharge)
        user_permissions = self.session.exec(
            select(PermissionUtilisateur).where(
                PermissionUtilisateur.utilisateur_id == user.id,
                PermissionUtilisateur.expire_le.is_(None) | (PermissionUtilisateur.expire_le > datetime.now(timezone.utc))
            )
        ).all()
        
        for perm in user_permissions:
            permissions[perm.ressource] = perm.niveau_permission
        
        return permissions
    
    def has_permission(self, user: User, resource: TypeRessource, required_level: NiveauPermission) -> bool:
        """Vérifie si un utilisateur a la permission requise"""
        user_permissions = self.get_user_permissions(user)
        
        if resource not in user_permissions:
            return False
        
        user_level = user_permissions[resource]
        
        # Hiérarchie des permissions
        level_hierarchy = {
            NiveauPermission.LECTURE: 1,
            NiveauPermission.ECRITURE: 2,
            NiveauPermission.SUPPRESSION: 3,
            NiveauPermission.ADMIN: 4
        }
        
        return level_hierarchy.get(user_level, 0) >= level_hierarchy.get(required_level, 0)
    
    def grant_permission(self, user: User, target_user_id: int, resource: TypeRessource, 
                        permission_level: NiveauPermission, reason: str = None) -> bool:
        """Accorde une permission spécifique à un utilisateur"""
        try:
            # Vérifier que l'utilisateur peut accorder cette permission
            if not self.has_permission(user, resource, NiveauPermission.ADMIN):
                return False
            
            # Créer ou mettre à jour la permission
            existing = self.session.exec(
                select(PermissionUtilisateur).where(
                    PermissionUtilisateur.utilisateur_id == target_user_id,
                    PermissionUtilisateur.ressource == resource
                )
            ).first()
            
            old_permission = existing.niveau_permission if existing else None
            
            if existing:
                existing.niveau_permission = permission_level
                existing.accordee_par = user.id
                existing.cree_le = datetime.now(timezone.utc)
            else:
                new_permission = PermissionUtilisateur(
                    utilisateur_id=target_user_id,
                    ressource=resource,
                    niveau_permission=permission_level,
                    accordee_par=user.id
                )
                self.session.add(new_permission)
            
            # Log de la permission
            log = LogPermission(
                utilisateur_id=user.id,
                utilisateur_cible_id=target_user_id,
                action="ACCORDER",
                ressource=resource,
                ancienne_permission=old_permission,
                nouvelle_permission=permission_level,
                raison=reason
            )
            self.session.add(log)
            
            self.session.commit()
            return True
            
        except Exception as e:
            self.session.rollback()
            print(f"Erreur lors de l'octroi de permission: {e}")
            return False
    
    def revoke_permission(self, user: User, target_user_id: int, resource: TypeRessource, 
                         reason: str = None) -> bool:
        """Révoque une permission spécifique d'un utilisateur"""
        try:
            if not self.has_permission(user, resource, NiveauPermission.ADMIN):
                return False
            
            existing = self.session.exec(
                select(PermissionUtilisateur).where(
                    PermissionUtilisateur.utilisateur_id == target_user_id,
                    PermissionUtilisateur.ressource == resource
                )
            ).first()
            
            if existing:
                old_permission = existing.niveau_permission
                self.session.delete(existing)
                
                # Log de la révocation
                log = LogPermission(
                    utilisateur_id=user.id,
                    utilisateur_cible_id=target_user_id,
                    action="REVOQUER",
                    ressource=resource,
                    ancienne_permission=old_permission,
                    raison=reason
                )
                self.session.add(log)
                
                self.session.commit()
                return True
            
            return False
            
        except Exception as e:
            self.session.rollback()
            print(f"Erreur lors de la révocation de permission: {e}")
            return False
    
    def get_permission_matrix(self) -> Dict[str, Dict[TypeRessource, NiveauPermission]]:
        """Récupère la matrice complète des permissions par rôle"""
        matrix = {}
        
        role_permissions = self.session.exec(select(PermissionRole)).all()
        
        for perm in role_permissions:
            if perm.role not in matrix:
                matrix[perm.role] = {}
            matrix[perm.role][perm.ressource] = perm.niveau_permission
        
        return matrix
    
    def initialize_default_permissions(self):
        """Initialise les permissions par défaut pour chaque rôle"""
        default_permissions = {
            # ADMINISTRATEUR - Tous les droits
            UserRole.ADMINISTRATEUR.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.ADMIN,
                TypeRessource.PROGRAMMES: NiveauPermission.ADMIN,
                TypeRessource.CANDIDATS: NiveauPermission.ADMIN,
                TypeRessource.INSCRIPTIONS: NiveauPermission.ADMIN,
                TypeRessource.JURYS: NiveauPermission.ADMIN,
                TypeRessource.DOCUMENTS: NiveauPermission.ADMIN,
                TypeRessource.LOGS: NiveauPermission.ADMIN,
                TypeRessource.PARAMETRES: NiveauPermission.ADMIN,
                TypeRessource.SAUVEGARDE: NiveauPermission.ADMIN,
                TypeRessource.ARCHIVE: NiveauPermission.ADMIN,
            },
            # DIRECTEUR GENERAL - Droits étendus
            UserRole.DIRECTEUR_GENERAL.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.ECRITURE,
                TypeRessource.PROGRAMMES: NiveauPermission.ADMIN,
                TypeRessource.CANDIDATS: NiveauPermission.ECRITURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.ECRITURE,
                TypeRessource.JURYS: NiveauPermission.ECRITURE,
                TypeRessource.DOCUMENTS: NiveauPermission.ECRITURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.ECRITURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.ECRITURE,
                TypeRessource.ARCHIVE: NiveauPermission.ECRITURE,
            },
            # DIRECTEUR TECHNIQUE - Droits techniques
            UserRole.DIRECTEUR_TECHNIQUE.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.LECTURE,
                TypeRessource.PROGRAMMES: NiveauPermission.ECRITURE,
                TypeRessource.CANDIDATS: NiveauPermission.ECRITURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.ECRITURE,
                TypeRessource.JURYS: NiveauPermission.ECRITURE,
                TypeRessource.DOCUMENTS: NiveauPermission.ECRITURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.ECRITURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            },
            # RESPONSABLE PROGRAMME - Gestion de programme
            UserRole.RESPONSABLE_PROGRAMME.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.LECTURE,
                TypeRessource.PROGRAMMES: NiveauPermission.ECRITURE,
                TypeRessource.CANDIDATS: NiveauPermission.ECRITURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.ECRITURE,
                TypeRessource.JURYS: NiveauPermission.ECRITURE,
                TypeRessource.DOCUMENTS: NiveauPermission.ECRITURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.LECTURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            },
            # CONSEILLER - Accompagnement candidats
            UserRole.CONSEILLER.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.LECTURE,
                TypeRessource.PROGRAMMES: NiveauPermission.LECTURE,
                TypeRessource.CANDIDATS: NiveauPermission.ECRITURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.ECRITURE,
                TypeRessource.JURYS: NiveauPermission.LECTURE,
                TypeRessource.DOCUMENTS: NiveauPermission.ECRITURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.LECTURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            },
            # COORDINATEUR - Coordination
            UserRole.COORDINATEUR.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.LECTURE,
                TypeRessource.PROGRAMMES: NiveauPermission.LECTURE,
                TypeRessource.CANDIDATS: NiveauPermission.ECRITURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.ECRITURE,
                TypeRessource.JURYS: NiveauPermission.LECTURE,
                TypeRessource.DOCUMENTS: NiveauPermission.ECRITURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.LECTURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            },
            # FORMATEUR - Formation
            UserRole.FORMATEUR.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.LECTURE,
                TypeRessource.PROGRAMMES: NiveauPermission.LECTURE,
                TypeRessource.CANDIDATS: NiveauPermission.LECTURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.LECTURE,
                TypeRessource.JURYS: NiveauPermission.LECTURE,
                TypeRessource.DOCUMENTS: NiveauPermission.LECTURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.LECTURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            },
            # EVALUATEUR - Évaluation
            UserRole.EVALUATEUR.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.LECTURE,
                TypeRessource.PROGRAMMES: NiveauPermission.LECTURE,
                TypeRessource.CANDIDATS: NiveauPermission.LECTURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.LECTURE,
                TypeRessource.JURYS: NiveauPermission.ECRITURE,
                TypeRessource.DOCUMENTS: NiveauPermission.LECTURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.LECTURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            },
            # ACCOMPAGNATEUR - Accompagnement
            UserRole.ACCOMPAGNATEUR.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.LECTURE,
                TypeRessource.PROGRAMMES: NiveauPermission.LECTURE,
                TypeRessource.CANDIDATS: NiveauPermission.ECRITURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.LECTURE,
                TypeRessource.JURYS: NiveauPermission.LECTURE,
                TypeRessource.DOCUMENTS: NiveauPermission.LECTURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.LECTURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            },
            # DRH - Ressources humaines
            UserRole.DRH.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.ECRITURE,
                TypeRessource.PROGRAMMES: NiveauPermission.LECTURE,
                TypeRessource.CANDIDATS: NiveauPermission.LECTURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.LECTURE,
                TypeRessource.JURYS: NiveauPermission.LECTURE,
                TypeRessource.DOCUMENTS: NiveauPermission.LECTURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.LECTURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            },
            # RESPONSABLE STRUCTURE - Gestion structure
            UserRole.RESPONSABLE_STRUCTURE.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.LECTURE,
                TypeRessource.PROGRAMMES: NiveauPermission.LECTURE,
                TypeRessource.CANDIDATS: NiveauPermission.ECRITURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.ECRITURE,
                TypeRessource.JURYS: NiveauPermission.LECTURE,
                TypeRessource.DOCUMENTS: NiveauPermission.ECRITURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.LECTURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            },
            # COACH EXTERNE - Coaching externe
            UserRole.COACH_EXTERNE.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.LECTURE,
                TypeRessource.PROGRAMMES: NiveauPermission.LECTURE,
                TypeRessource.CANDIDATS: NiveauPermission.LECTURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.LECTURE,
                TypeRessource.JURYS: NiveauPermission.LECTURE,
                TypeRessource.DOCUMENTS: NiveauPermission.LECTURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.LECTURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            },
            # JURY EXTERNE - Jury externe
            UserRole.JURY_EXTERNE.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.LECTURE,
                TypeRessource.PROGRAMMES: NiveauPermission.LECTURE,
                TypeRessource.CANDIDATS: NiveauPermission.LECTURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.LECTURE,
                TypeRessource.JURYS: NiveauPermission.ECRITURE,
                TypeRessource.DOCUMENTS: NiveauPermission.LECTURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.LECTURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            },
            # CANDIDAT - Candidat
            UserRole.CANDIDAT.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.LECTURE,
                TypeRessource.PROGRAMMES: NiveauPermission.LECTURE,
                TypeRessource.CANDIDATS: NiveauPermission.LECTURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.LECTURE,
                TypeRessource.JURYS: NiveauPermission.LECTURE,
                TypeRessource.DOCUMENTS: NiveauPermission.LECTURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.LECTURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            },
            # RESPONSABLE COMMUNICATION - Communication
            UserRole.RESPONSABLE_COMMUNICATION.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.LECTURE,
                TypeRessource.PROGRAMMES: NiveauPermission.LECTURE,
                TypeRessource.CANDIDATS: NiveauPermission.LECTURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.LECTURE,
                TypeRessource.JURYS: NiveauPermission.LECTURE,
                TypeRessource.DOCUMENTS: NiveauPermission.ECRITURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.LECTURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            },
            # ASSISTANT COMMUNICATION - Assistant communication
            UserRole.ASSISTANT_COMMUNICATION.value: {
                TypeRessource.UTILISATEURS: NiveauPermission.LECTURE,
                TypeRessource.PROGRAMMES: NiveauPermission.LECTURE,
                TypeRessource.CANDIDATS: NiveauPermission.LECTURE,
                TypeRessource.INSCRIPTIONS: NiveauPermission.LECTURE,
                TypeRessource.JURYS: NiveauPermission.LECTURE,
                TypeRessource.DOCUMENTS: NiveauPermission.LECTURE,
                TypeRessource.LOGS: NiveauPermission.LECTURE,
                TypeRessource.PARAMETRES: NiveauPermission.LECTURE,
                TypeRessource.SAUVEGARDE: NiveauPermission.LECTURE,
                TypeRessource.ARCHIVE: NiveauPermission.LECTURE,
            }
        }
        
        for role, permissions in default_permissions.items():
            for resource, level in permissions.items():
                # Vérifier si la permission existe déjà
                existing = self.session.exec(
                    select(PermissionRole).where(
                        PermissionRole.role == role,
                        PermissionRole.ressource == resource
                    )
                ).first()
                
                if not existing:
                    new_permission = PermissionRole(
                        role=role,
                        ressource=resource,
                        niveau_permission=level
                    )
                    self.session.add(new_permission)
        
        self.session.commit()
    
    def update_role_permission(self, role: str, resource: TypeRessource, 
                               permission_level: NiveauPermission, user: User) -> bool:
        """Met à jour une permission de rôle"""
        try:
            # Vérifier que l'utilisateur peut modifier les permissions
            if not self.has_permission(user, TypeRessource.PARAMETRES, NiveauPermission.ADMIN):
                return False
            
            # Trouver ou créer la permission
            existing = self.session.exec(
                select(PermissionRole).where(
                    PermissionRole.role == role,
                    PermissionRole.ressource == resource
                )
            ).first()
            
            old_permission = existing.niveau_permission if existing else None
            
            if existing:
                existing.niveau_permission = permission_level
                existing.modifie_le = datetime.now(timezone.utc)
            else:
                new_permission = PermissionRole(
                    role=role,
                    ressource=resource,
                    niveau_permission=permission_level
                )
                self.session.add(new_permission)
            
            # Log de la modification
            log = LogPermission(
                utilisateur_id=user.id,
                action="MODIFIER_ROLE",
                ressource=resource,
                ancienne_permission=old_permission,
                nouvelle_permission=permission_level,
                raison=f"Modification permission rôle {role}"
            )
            self.session.add(log)
            
            self.session.commit()
            return True
            
        except Exception as e:
            self.session.rollback()
            print(f"Erreur lors de la modification de permission: {e}")
            return False
    
    def get_all_roles(self) -> List[str]:
        """Récupère tous les rôles disponibles"""
        return [role.value for role in UserRole]
