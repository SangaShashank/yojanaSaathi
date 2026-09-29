"""Phase 7 application-scoped evidence, decode, and bounded recovery state transitions."""
import hashlib
from sqlalchemy.orm import Session
from backend.app.db.repositories.application_repository import ApplicationRepository
from backend.app.db.repositories.event_repository import EventRepository
from backend.app.db.models.rejection import RejectionEvent, RejectionEvidence, RejectionDecode, RecoveryActionRecord
from backend.app.schemas.rejection import RejectionEvidenceRequest, RecoveryStateResponse
from backend.app.services.rejection_decoder import RejectionDecoder

class RejectionRecoveryService:
 def _app(self,db,case_id,app_id):
  app=ApplicationRepository.get_application(db,app_id)
  if not app or app.case_id!=case_id: raise ValueError("Application does not belong to this case.")
  return app
 def claim(self,db,case_id,app_id):
  app=self._app(db,case_id,app_id); event=RejectionEvent(application_id=app_id); db.add(event); app.status="REJECTION_EVIDENCE_REQUIRED"; db.commit(); db.refresh(event)
  EventRepository.record_application_event(db,app_id,"REJECTION_CLAIMED",{"rejection_event_id":event.id})
  EventRepository.record_application_event(db,app_id,"REJECTION_EVIDENCE_REQUESTED",{"rejection_event_id":event.id})
  return self.state(db,case_id,app_id)
 def evidence(self,db,case_id,app_id,event_id,payload:RejectionEvidenceRequest):
  self._app(db,case_id,app_id); event=db.query(RejectionEvent).filter_by(id=event_id,application_id=app_id).first()
  if not event: raise ValueError("Rejection event does not belong to this application.")
  if payload.source_type not in {"SMS","SCREENSHOT","LETTER","PORTAL_TEXT","CODE","MANUAL_ENTRY"}: raise ValueError("Unsupported evidence source type.")
  if not (payload.raw_text or payload.rejection_code): raise ValueError("Official evidence text or code is required.")
  raw=(payload.raw_text or "")+"|"+(payload.rejection_code or ""); digest=hashlib.sha256(raw.encode()).hexdigest()
  old=db.query(RejectionEvidence).filter_by(application_id=app_id,content_hash=digest).first()
  if old:
   event.evidence_id=old.id; event.status="REJECTION_EVIDENCE_RECEIVED"; event.recovery_status="REJECTION_EVIDENCE_RECEIVED"; db.commit(); return old
  evidence=RejectionEvidence(rejection_event_id=event.id,application_id=app_id,source_type=payload.source_type,raw_text=payload.raw_text,rejection_code=payload.rejection_code,content_hash=digest,provided_by=payload.provided_by,status="VERIFIED")
  db.add(evidence); db.flush(); event.evidence_id=evidence.id; event.status="REJECTION_EVIDENCE_RECEIVED"; event.recovery_status="REJECTION_EVIDENCE_RECEIVED"; db.commit(); db.refresh(evidence)
  EventRepository.record_application_event(db,app_id,"REJECTION_EVIDENCE_RECEIVED",{"rejection_event_id":event.id,"evidence_id":evidence.id,"source_type":payload.source_type})
  return evidence
 def decode(self,db,case_id,app_id,event_id):
  app=self._app(db,case_id,app_id); event=db.query(RejectionEvent).filter_by(id=event_id,application_id=app_id).first()
  if not event or not event.evidence_id: raise ValueError("Validated rejection evidence is required before decoding.")
  evidence=db.query(RejectionEvidence).filter_by(id=event.evidence_id).first(); current=db.query(RejectionDecode).filter_by(evidence_id=evidence.id,is_current=True).first()
  if current: return self._decode_model(evidence.id,current)
  result=RejectionDecoder.decode(evidence.id,evidence.raw_text,evidence.rejection_code)
  rec=RejectionDecode(evidence_id=evidence.id,status=result.status,categories={"items":result.categories},matched_codes={"items":result.matched_codes},matched_signals={"items":result.matched_signals},is_current=True); db.add(rec)
  event.decoded_status=result.status; event.status="REJECTED"; event.recovery_status="RECOVERY_REQUIRED" if result.status=="SUPPORTED" else "HUMAN_VERIFICATION_REQUIRED"; app.status="REJECTED" if result.status=="SUPPORTED" else "HUMAN_VERIFICATION_REQUIRED"; db.commit()
  EventRepository.record_application_event(db,app_id,"REJECTION_DECODED",{"rejection_event_id":event.id,"status":result.status,"categories":result.categories})
  if result.requires_human_verification: EventRepository.record_application_event(db,app_id,"REJECTION_ESCALATED",{"rejection_event_id":event.id})
  return result
 def recovery_action(self,db,case_id,app_id,event_id,action,evidence_note=None):
  app=self._app(db,case_id,app_id); event=db.query(RejectionEvent).filter_by(id=event_id,application_id=app_id).first()
  if not event or event.recovery_status not in {"RECOVERY_REQUIRED","RECOVERY_IN_PROGRESS"}: raise ValueError("Recovery action is not currently permitted.")
  if action not in {"REQUEST_RECOVERY_DOCUMENT","REQUEST_RECOVERY_CLARIFICATION","RESOLVE_REJECTION","REASSESS_APPLICATION"}: raise ValueError("Unsupported recovery action.")
  if action=="RESOLVE_REJECTION" and not evidence_note: raise ValueError("Recovery evidence is required; a citizen statement alone is insufficient.")
  rec=RecoveryActionRecord(rejection_event_id=event.id,application_id=app_id,action=action,status="COMPLETED" if action=="RESOLVE_REJECTION" else "REQUESTED",metadata_json={"evidence_note_present":bool(evidence_note)}); db.add(rec)
  if action=="RESOLVE_REJECTION": event.recovery_status="RECOVERY_COMPLETED"; app.status="RECOVERY_COMPLETED"; EventRepository.record_application_event(db,app_id,"RECOVERY_RESOLVED",{"rejection_event_id":event.id})
  else: event.recovery_status="RECOVERY_IN_PROGRESS"; app.status="RECOVERY_IN_PROGRESS"; EventRepository.record_application_event(db,app_id,"RECOVERY_ACTION_REQUESTED",{"rejection_event_id":event.id,"action":action})
  db.commit(); return self.state(db,case_id,app_id)
 def state(self,db,case_id,app_id):
  app=self._app(db,case_id,app_id); event=db.query(RejectionEvent).filter_by(application_id=app_id).order_by(RejectionEvent.received_at.desc()).first(); cats=[]; human=False; next_action=None
  if event and event.evidence_id:
   decode=db.query(RejectionDecode).join(RejectionEvidence).filter(RejectionEvidence.id==event.evidence_id,RejectionDecode.is_current==True).first()
   if decode: cats=decode.categories.get("items",[]); human=decode.status!="SUPPORTED"
  recovery=event.recovery_status if event else "NONE"
  if recovery=="REJECTION_EVIDENCE_REQUIRED": next_action="REQUEST_REJECTION_EVIDENCE"
  elif recovery=="REJECTION_EVIDENCE_RECEIVED": next_action="DECODE_REJECTION"
  elif recovery=="RECOVERY_REQUIRED": next_action="REQUEST_RECOVERY_DOCUMENT"
  elif human: next_action="ESCALATE_HUMAN"
  return RecoveryStateResponse(application_id=app_id,status=app.status,recovery_status=recovery,rejection_categories=cats,next_action=next_action,human_verification_required=human)
 @staticmethod
 def _decode_model(evidence_id,row):
  from backend.app.schemas.rejection import RejectionDecodeResult
  return RejectionDecodeResult(evidence_id=evidence_id,status=row.status,categories=row.categories.get("items",[]),matched_codes=row.matched_codes.get("items",[]),matched_signals=row.matched_signals.get("items",[]),requires_human_verification=row.status!="SUPPORTED")
