"""
Skills-Taps: Mission Control (Observability Layer)
=================================================
Automated OpenTelemetry tracing for Skillsmith missions.
Integrates with Arize Phoenix (local) or LangWatch (cloud).
"""

import os
from pathlib import Path
from typing import Optional
import logging

# Feature Flag: Only activate if dependencies are present
try:
    from phoenix.otel import register
    from opentelemetry import trace
    HAS_TRACING = True
except ImportError:
    HAS_TRACING = False

class MissionControl:
    """Orchestrates local and cloud tracing for Skillsmith missions."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.tracer = None
        
    def activate(self, endpoint: str = "http://localhost:6006/v1/traces"):
        """Activate the OpenTelemetry tracer using Arize Phoenix Gold Standard for CLI Tools."""
        if not HAS_TRACING:
            return False
            
        try:
            from opentelemetry import trace
            project_name = f"skillsmith:{self.project_root.name}"
            
            # 1. Environment Sync (Secondary Safety)
            os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = endpoint
            os.environ["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/protobuf"
            os.environ["PHOENIX_PROJECT_NAME"] = project_name
            os.environ["OTEL_SERVICE_NAME"] = project_name
            
            # 2. Skip if already active (Prevent "Overriding is not allowed")
            from opentelemetry import trace
            if not isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider):
                self.tracer = trace.get_tracer("skillsmith")
                return True
            
            # 3. Official Arize Phoenix Sync Registration
            # batch=False: Forces synchronous delivery for short-lived CLI tools
            # auto_instrument=True: Automatically captures underlying OpenAI/LLM calls
            register(
                project_name=project_name,
                endpoint=endpoint,
                batch=False,
                auto_instrument=True
            )
            
            self.tracer = trace.get_tracer("skillsmith")
            
            # 5. Global Heartbeat (L4 Trace Generation)
            # Protected: If dash isn't already running, this will sync-fail silently
            try:
                with self.tracer.start_as_current_span(
                    "watcher:heartbeat", 
                    attributes={"status": "connected", "mode": "sync"}
                ):
                    pass
            except Exception:
                pass
                
            return True
        except Exception as e:
            logging.error(f"Failed to activate Mission Control: {e}")
            return False

    def start_span(self, name: str, attributes: Optional[dict] = None):
        """Start a new trace span (A Thinking Node)."""
        from contextlib import nullcontext
        if not self.tracer:
            # Self-heal on access
            if self.activate():
                pass
            else:
                return nullcontext()
        
        try:
            return self.tracer.start_as_current_span(name, attributes=attributes or {})
        except:
            return nullcontext()

class MissionAuditor:
    """Provides the 'Eyes' for our agents to self-correct from Mission Control."""
    
    def __init__(self, endpoint: str = "http://localhost:6006"):
        self.endpoint = endpoint
        self._client = None
        
    @property
    def client(self):
        if not self._client and HAS_TRACING:
            try:
                from phoenix import Client
                self._client = Client(endpoint=self.endpoint)
            except:
                pass
        return self._client

    def get_latest_mission_trace(self, project_name: str) -> Optional[dict]:
        """Fetch the latest real swarm mission, ignoring internal watcher heartbeats."""
        if not self.client:
            return None
            
        try:
            # 1. Fetch the full project spans
            df = self.client.get_spans_dataframe(project_name=project_name)
            
            if df is None or (hasattr(df, 'empty') and df.empty):
                return None
            
            # 2. Identify the latest root mission, but IGNORE internal heartbeats
            import pandas as pd
            # Filter: name must NOT be 'watcher:heartbeat'
            mask = (
                ((df['name'] == 'swarm_execution') | (df['parent_id'].isna())) & 
                (df['name'] != 'watcher:heartbeat')
            )
            filtered = df[mask].sort_values(by='start_time', ascending=False)
            
            if filtered.empty:
                return None
            
            latest = filtered.iloc[0]
            
            # 3. Robust Attribute Resolution
            goal = None
            for col in ['attributes.goal', 'goal', 'name']:
                if col in latest and not (isinstance(latest[col], float) and pd.isna(latest[col])):
                    goal = latest[col]
                    break
            
            status = latest.get("status_code", "UNKNOWN")
            if status == "UNSET":
                status = "OK (SUCCESS)"
            
            return {
                "trace_id": latest.get("context.trace_id", "Unknown"),
                "status": status,
                "goal": goal or "Unknown Mission",
                "start_time": str(latest.get("start_time"))
            }
        except Exception as e:
            logging.error(f"Failed to query mission trace: {e}")
            return None

    def get_mission_bottlenecks(self, trace_id: str) -> list[dict]:
        """Identify failed spans in a specific mission via DataFrame filtering."""
        if not self.client:
            return []
            
        try:
            df = self.client.get_spans_dataframe()
            if df is None or (hasattr(df, 'empty') and df.empty):
                return []
            
            # Filter for the specific trace and errors
            # Some versions use 'context.trace_id', others 'trace_id'
            trace_col = 'context.trace_id' if 'context.trace_id' in df.columns else 'trace_id'
            if trace_col not in df.columns:
                return []
                
            mask = (df[trace_col] == trace_id) & (df['status_code'] == 'ERROR')
            failures = df[mask]
            
            if failures.empty:
                return []
            
            # Convert failures to dict list
            results = []
            for _, row in failures.iterrows():
                # Extract error message across variants
                err_msg = row.get("attributes.exception.message") or row.get("attributes.error.message") or "Unknown termination"
                results.append({
                    "name": row.get("name", "Unnamed Span"),
                    "attributes": {"exception.message": str(err_msg)}
                })
            
            return results
        except Exception as e:
            logging.error(f"Failed to query bottlenecks: {e}")
            return []

def get_mission_control(cwd: Path) -> MissionControl:
    """Helper to get and initialize MissionControl."""
    mc = MissionControl(cwd)
    # Check for LANGWATCH_API_KEY for cloud, or default to local Phoenix
    if os.getenv("LANGWATCH_API_KEY"):
        # LangWatch logic would go here
        pass
    else:
        mc.activate()
    return mc
