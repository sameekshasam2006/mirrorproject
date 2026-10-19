from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db import get_db
from app.models.models import Simulation, User
from app.schemas.schemas import SimulationInput, SimulationOut
from app.services.simulation_engine import approve_simulation, simulate_decision

router = APIRouter()


@router.post("/run", response_model=SimulationOut)
def run_simulation(payload: SimulationInput, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    try:
        simulation, impact = simulate_decision(
            db,
            current_user,
            payload.task_id,
            payload.scenario_type,
            new_time=payload.new_time,
            new_duration=payload.new_duration,
            new_priority=payload.new_priority,
            move_to_date=payload.move_to_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    simulation_dict = {
        "id": simulation.id,
        "user_id": simulation.user_id,
        "title": simulation.title,
        "scenario_type": simulation.scenario_type,
        "original_snapshot": simulation.original_snapshot,
        "proposed_snapshot": simulation.proposed_snapshot,
        "impact_analysis": simulation.impact_analysis,
        "feasibility_result": simulation.feasibility_result,
        "status": simulation.status,
        "created_at": simulation.created_at,
        "updated_at": simulation.updated_at,
        "alternatives": [],
    }
    return simulation_dict


@router.get("/history", response_model=list[SimulationOut])
def get_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    simulations = db.query(Simulation).filter(Simulation.user_id == current_user.id).order_by(Simulation.created_at.desc()).all()
    return [
        {
            "id": sim.id,
            "user_id": sim.user_id,
            "title": sim.title,
            "scenario_type": sim.scenario_type,
            "original_snapshot": sim.original_snapshot,
            "proposed_snapshot": sim.proposed_snapshot,
            "impact_analysis": sim.impact_analysis,
            "feasibility_result": sim.feasibility_result,
            "status": sim.status,
            "created_at": sim.created_at,
            "updated_at": sim.updated_at,
            "alternatives": [],
        }
        for sim in simulations
    ]


@router.post("/{simulation_id}/approve")
def approve(simulation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    try:
        result = approve_simulation(db, current_user, simulation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result
