"""Publish numeric/event facts only; originals remain private and unchanged."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
b=Path('/workspace/2246-granite-activation')
p=b/'private/render-original-3.json'
raw=json.loads(p.read_text());record=json.loads(next(x['text'] for x in raw['content'] if x.get('type')=='text'))
rows=[]
for row in record['logs']:
 try:m=json.loads(row['message'])
 except (ValueError,TypeError):continue
 d=m.get('diagnostic') or {}
 if m.get('event')=='diagnostic_boundary':
  selected={k:d[k] for k in ('name','boundary','timestamp','status','duration_ms','span_id','parent_span_id','elapsed_from_trace_ms') if k in d}
  if d.get('name')=='memory_sample':
   mem=d['memory'];selected['memory']={k:mem[k] for k in ('cgroup_current_bytes','cgroup_limit_bytes','cgroup_inactive_file_bytes','cgroup_anonymous_bytes','cgroup_memory_events','rss_bytes','observer_pid','observer_kind','active_process_count','zombie_count','sampling_incomplete','process_samples_are_sequential','capture_duration_ms') if k in mem}
   resident=mem.get('runtime_residency',{});selected['residency']={k:resident[k] for k in ('resident_count','warm_limit','hydrating_count','warm_count','runtime_samples_truncated') if k in resident}
   selected['residency']['runtimes']=[dict(role='target' if x.get('scope')=='ae041fd655d87f3c' else 'other_current',**{k:x[k] for k in ('state','active_requests','pinned','owns_state','background_tasks','source_generation_count') if k in x}) for x in resident.get('runtimes',[])]
   selected['requested_boundaries']=[{k:x[k] for k in ('name','boundary','requested_at','request_id') if k in x} for x in d.get('requested_boundaries',[])]
  rows.append(dict(timestamp=row['timestamp'],request_id=m.get('request_id'),event=m['event'],facts=selected))
 elif m.get('event') in ('request_started','request_complete'):
  rows.append(dict(timestamp=row['timestamp'],request_id=m.get('request_id'),event=m['event'],**{k:m[k] for k in ('method','status_code','duration_ms') if k in m}))
report=dict(schema=1,prepared_at=datetime.now(timezone.utc).isoformat(),source='Authorized read-only Render logs, full retained narrow request window; no new request or restoration',historical=True,not_current_admission=True,complete_tool_window=record['hasMore'] is False,private_original_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),records=rows,omitted=['client IP and HTTP query/user context','opaque service/log labels','unneeded runtime identifiers','unrelated process names/IDs','private source records, credentials and cache payloads were not requested'],limitations=['Queued memory capture follows failure; it is not the guard input.','Original exception type/traceback and cleanup result were not emitted by deployed activation handling.','Runtime DEFERRED and acquired cache phase support the typed admission path from source; no exact historical branch input or fatal allocation is proved.','One serving process does not establish idleness in other processes.','Source-generation key count is not a count of retained version copies.'])
(b/'incident-observations.json').write_text(json.dumps(report,indent=2)+'\n')
print('Sanitized',len(rows),'retained events; private original unchanged')
