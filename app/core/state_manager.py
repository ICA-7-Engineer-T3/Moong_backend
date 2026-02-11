
"""
State Manager for MOONG System (Shared Context)
- Works as the bridge between MOONG-1 and MOONG-2
- Reads/Writes current_persona and guidelines from Firebase
"""

from typing import Dict, Any, Optional
from datetime import datetime
import json
import traceback

# Reuse existing Firebase Config
from app.modules.moong_v2.core.firebase_config import firebase_config

class StateManager:
    """공유 컨텍스트 관리자 (Firebase Wrapper)"""
    
    def __init__(self):
        self.collection_name = "moong_personas" # Changed from 'moongs' for clarity or use 'moong_users'
        # But instructions said 'moongs' collection contains current_persona/guidelines.
        # Let's stick to instruction: "moongs 컬렉션에 저장된 current_persona..."
        self.collection_name = "moongs" 
        self.db = firebase_config.get_db()

    def get_user_persona(self, user_id: str) -> Dict[str, Any]:
        """
        MOONG-1 Engine uses this to READ the current persona.
        """
        if not self.db:
            print("[StateManager] DB not initialized, trying to simple init")
            firebase_config.initialize_firebase()
            self.db = firebase_config.get_db()
            
        try:
            doc_ref = self.db.collection(self.collection_name).document(user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                return {
                    "current_persona": data.get("current_persona", "mate"), # default mate
                    "guidelines": data.get("guidelines", {}),
                    "context_summary": data.get("context_summary", ""),
                    "turn_count": data.get("turn_count", 0)
                }
            else:
                # If no persona exists, return default
                print(f"[StateManager] No persona found for {user_id}, returning default.")
                return self._get_default_persona()
                
        except Exception as e:
            print(f"[StateManager] Error reading persona: {e}")
            return self._get_default_persona()

    def update_user_persona(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """
        MOONG-2 Engine uses this to WRITE/UPDATE the persona.
        """
        if not self.db:
            firebase_config.initialize_firebase()
            self.db = firebase_config.get_db()
            
        try:
            doc_ref = self.db.collection(self.collection_name).document(user_id)
            
            # Add timestamp
            update_data["updated_at"] = datetime.now()
            
            # Use set with merge=True to creating if not exists or updating fields
            doc_ref.set(update_data, merge=True)
            print(f"[StateManager] Updated persona for {user_id}")
            return True
            
        except Exception as e:
            print(f"[StateManager] Error updating persona: {e}")
            return False

    def increment_turn_count(self, user_id: str) -> int:
        """
        MOONG-2 Engine uses this to increment turn count.
        Returns new turn count.
        """
        if not self.db:
             firebase_config.initialize_firebase()
             self.db = firebase_config.get_db()

        try:
            doc_ref = self.db.collection(self.collection_name).document(user_id)
            
            # Transactional increment could be better, but acceptable for now
            # Using simple get-update for simplicity in MVP
            doc = doc_ref.get()
            current_turn = 0
            if doc.exists:
                current_turn = doc.to_dict().get("turn_count", 0)
            
            new_turn = current_turn + 1
            doc_ref.set({"turn_count": new_turn, "last_interaction": datetime.now()}, merge=True)
            
            return new_turn
        except Exception as e:
            print(f"[StateManager] Error incrementing turn: {e}")
            return 0
            
    def _get_default_persona(self):
        return {
            "current_persona": "mate", 
            "guidelines": {
                "tone": "friendly",
                "emoji": "frequent"
            },
            "context_summary": "",
            "turn_count": 0
        }

# Global Instance
state_manager = StateManager()
