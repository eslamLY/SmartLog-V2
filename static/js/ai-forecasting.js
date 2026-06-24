const API={master:'/api/ai/master-forecast',leave:'/api/ai/leave-forecast',absence:'/api/ai/absence-forecast',shortage:'/api/ai/shortage-forecast',turnover:'/api/ai/turnover-forecast',hiring:'/api/ai/hiring-forecast',daily:'/api/ai/daily-forecast',calendar:'/api/ai/calendar',recommendations:'/api/ai/recommendations',smartRecs:'/api/ai/smart-recommendations',leaveDetail:function(e){return'/api/ai/employee/'+e+'/leave-detail'},absenceDetail:function(e){return'/api/ai/employee/'+e+'/absence-detail'},turnoverDetail:function(e){return'/api/ai/employee/'+e+'/turnover-detail'},simulate:'/api/ai/simulate',trendsLeave:'/api/ai/trends/leave',trendsAbsence:'/api/ai/trends/absence',trendsTurnover:'/api/ai/trends/turnover',trendsStaffing:'/api/ai/trends/staffing',liveStatus:'/api/ai/live-status',reportData:'/api/ai/report/data',reportCSV:'/api/ai/report/csv',modelPerf:'/api/ai/model-performance'};
let masterData=null,allEmployees=[];
function $(s,p){return(p||document).querySelector(s)}
function $$(s,p){return(p||document).querySelectorAll(s)}
async function getJSON(u){const m=document.querySelector('meta[name="csrf-token"]');const t=m?m.getAttribute('content'):'';const r=await fetch(u,{headers:{'X-CSRFToken':t}});if(!r.ok)throw new Error(await r.text());return r.json()}
async function postJSON(u,d){const m=document.querySelector('meta[name="csrf-token"]');const t=m?m.getAttribute('content'):'';const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':t},body:JSON.stringify(d)});if(!r.ok)throw new Error(await r.text());return r.json()}

// ─── TABS ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded',function(){
  const btns=$$('#tabBar .tab-btn'),contents={};
  btns.forEach(function(b){
    var tab=b.dataset.tab;
    b.addEventListener('click',function(){switchTab(tab)})
  });
  switchTab('dashboard');
  loadEmployeeList();
  loadScenarioDepts();
  refreshAll();
});
function switchTab(name){
  $$('.tab-btn').forEach(function(b){b.classList.toggle('active',b.dataset.tab===name)});
  $$('.tab-content').forEach(function(c){c.classList.toggle('active',c.id==='tab-'+name)});
  if(name==='trends')loadTrends();
  if(name==='live')loadLiveStatus();
  if(name==='models')loadModelPerformance();
}

// ─── DASHBOARD ─────────────────────────────────────────────
async function refreshAll(){
  document.querySelector('#tab-dashboard .ai-card:first-child')&&await loadMaster();
  await loadCalendar();
  await loadSmartRecs();
  await loadLiveCount();
}
async function loadMaster(){
  try{
    masterData=await getJSON(API.master);
    var grid=$('#forecastGrid');
    grid.innerHTML='';
    var cols=[
      {icon:'ti ti-calendar-check',color:'#8b5cf6',title:'إجازات متوقعة',d:'leave_forecast',badge:function(d){return d.total_expected+' موظف'},badgeCls:'purple',rows:[{l:'الإجازات المتوقعة',k:'total_expected'},{l:'عالية الخطورة',k:'high_risk_count'},{l:'متوسط الاحتمال',k:function(d){return(d.average_probability*100).toFixed(0)+'%'}},{l:'الأقسام',k:function(d){return Object.keys(d.department_risk||{}).slice(0,3).join(', ')||'—'}}]},
      {icon:'ti ti-user-x',color:'#f59e0b',title:'غياب متوقع',d:'absence_forecast',badge:function(d){return d.total_at_risk+' موظف'},badgeCls:'amber',rows:[{l:'المعرضون للغياب',k:'total_at_risk'},{l:'خطورة عالية',k:'high_risk_count'},{l:'خطورة متوسطة',k:'medium_risk_count'},{l:'الأقسام',k:function(d){return Object.keys(d.departments||{}).slice(0,3).join(', ')||'—'}}]},
      {icon:'ti ti-alert-triangle',color:'#ef4444',title:'نقص متوقع',d:'staff_shortage',badge:function(d){return d.critical_count+' حرج'},badgeCls:'red',rows:[{l:'أيام حرجة',k:'critical_count'},{l:'أيام تحذير',k:'warning_count'},{l:'أيام آمنة',k:'ok_count'},{l:'إجمالي العجز',k:function(d){var t=0;(d.shortages||[]).forEach(function(s){t+=Math.abs(s.gap||0)});return t}}]},
      {icon:'ti ti-users-x',color:'#ec4899',title:'مخاطر الرحيل',d:'turnover_risk',badge:function(d){return d.total_at_risk+' موظف'},badgeCls:'red',rows:[{l:'المعرضون للخطر',k:'total_at_risk'},{l:'خطورة عالية',k:'high_risk_count'},{l:'خطورة متوسطة',k:'medium_risk_count'},{l:'الأقسام',k:function(d){return Object.keys(d.departments||{}).slice(0,3).join(', ')||'—'}}]},
      {icon:'ti ti-user-plus',color:'#22c55e',title:'احتياجات التوظيف',d:'hiring_needs',badge:function(d){return d.total_hiring_needed+' مطلوب'},badgeCls:'green',rows:[{l:'إجمالي المطلوب',k:'total_hiring_needed'},{l:'تقاعد متوقع',k:'expected_retirements'},{l:'فقدان بالدوران',k:'expected_turnover_losses'},{l:'احتياجات النمو',k:'expected_growth_needs'}]},
      {icon:'ti ti-calendar',color:'#6366f1',title:'توقعات اليوم',d:'daily_forecast',badge:function(d){return d.total_available+' متاح'},badgeCls:function(d){return d.total_available>5?'green':d.total_available>2?'amber':'red'},rows:[{l:'التاريخ',k:'date'},{l:'اليوم',k:'weekday'},{l:'الإجمالي',k:'total_employees'},{l:'المتاح',k:'total_available'}]}
    ];
    cols.forEach(function(c){
      var d=getNested(masterData,c.d);
      if(!d)return;
      var b='<span class="ai-badge '+(typeof c.badgeCls==='function'?c.badgeCls(d):c.badgeCls)+'">'+(typeof c.badge==='function'?c.badge(d):c.badge)+'</span>';
      var r=c.rows.map(function(rw){return'<div class="stat-row"><span class="stat-label">'+rw.l+'</span><span class="stat-value">'+(typeof rw.k==='function'?rw.k(d):d[rw.k]??'—')+'</span></div>'}).join('');
      grid.insertAdjacentHTML('beforeend','<div class="ai-card"><div class="card-icon" style="background:'+c.color+'22;color:'+c.color+'"><i class="'+c.icon+'"></i></div><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><h3>'+c.title+'</h3>'+b+'</div>'+r+'</div>')
    });
  }catch(e){console.error('Master error:',e)}
}
function getNested(o,p){return p.split('.').reduce(function(a,k){return a&&a[k]},o)}

async function loadCalendar(){
  try{
    if(!masterData||!masterData.calendar)return;
    var cal=masterData.calendar;
    var grid=$('#forecastGrid');
    if(!cal.days||!cal.days.length)return;
    var html='<div class="ai-card" style="grid-column:1/-1"><div class="card-icon" style="background:#6366f122;color:#6366f1"><i class="ti ti-calendar-month"></i></div><h3>رؤية شهرية — '+(cal.month_name||'')+' '+(cal.year||'')+'</h3><div class="calendar-grid">';
    html+=['الأحد','الإثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت'].map(function(d){return'<div class="calendar-header">'+d+'</div>'}).join('');
    cal.days.forEach(function(d){
      var cls='normal';
      if(d.critical)cls='critical';else if(d.warning)cls='warning';
      if(d.is_today)cls+=' today';
      if(d.current_month===false)cls+=' other-month';
      html+='<div class="calendar-day '+cls+'"><span>'+d.day+'</span><div class="day-tooltip">'+d.date+'<br>إجازات: '+(d.leave_count||0)+'<br>غياب: '+(d.absence_count||0)+'<br>متاح: '+(d.working||'—')+'</div><div class="day-dot'+(d.leave_count&&d.absence_count?' both':d.leave_count?' leave':d.absence_count?' absence':'')+'"></div></div>'
    });
    html+='</div></div>';
    grid.insertAdjacentHTML('beforeend',html);
  }catch(e){console.error('Calendar error:',e)}
}

async function loadSmartRecs(){
  try{
    var data=await getJSON(API.smartRecs);
    var grid=$('#forecastGrid');
    if(!data.recommendations||!data.recommendations.length)return;
    var html='<div class="ai-card" style="grid-column:1/-1"><div class="card-icon" style="background:#10b98122;color:#10b981"><i class="ti ti-bulb"></i></div><h3>توصيات AI ذكية</h3>';
    data.recommendations.forEach(function(r){
      var sev=r.severity||'info',ic=r.icon||(sev==='critical'?'🔴':sev==='warning'?'🟡':'🔵');
      html+='<div class="rec-card '+sev+'"><span class="rec-icon">'+ic+'</span><div><div class="rec-title">'+r.title+'</div><div class="rec-msg">'+r.message+(r.confidence?' <span style="color:#8b5cf6">ثقة: '+r.confidence+'%</span>':'')+(r.action?'<br><span style="color:var(--accent);cursor:pointer" onclick="window.location.href=\''+r.action_url+'\'">→ '+r.action+'</span>':'')+'</div></div></div>'
    });
    html+='</div>';
    grid.insertAdjacentHTML('beforeend',html);
  }catch(e){console.error('Smart recs error:',e)}
}

async function loadLiveCount(){
  try{
    var data=await getJSON(API.liveStatus);
    var el=$('#liveCount');
    if(el)el.innerHTML='<i class="ti ti-users"></i> <span class="live-indicator '+(data.status||'online')+'"></span> '+data.available+'/'+data.total_employees+' متاح'
  }catch(e){}
}

// ─── EMPLOYEE LIST ─────────────────────────────────────────
async function loadEmployeeList(){
  try{
    var r=await fetch('/api/employees/list');
    if(!r.ok)return;
    allEmployees=await r.json();
    var opts='';
    (allEmployees||[]).forEach(function(e){opts+='<option value="'+e.id+'">'+e.name+' — '+e.department+'</option>'});
    $$('select[id$=EmployeeSelect], select[id$=Employee], select[id$=employee]').forEach(function(s){if(s.id!=='scenarioEmployee'&&s.id!=='reportEmployee'){var cur=s.value;s.innerHTML='<option value="">— اختر موظف —</option>'+opts;s.value=cur}});
    var sopts='';
    (allEmployees||[]).forEach(function(e){sopts+='<option value="'+e.id+'">'+e.name+'</option>'});
    var se=$('#scenarioEmployee');if(se)se.innerHTML='<option value="">— موظف —</option>'+sopts;
    var re=$('#reportEmployee');if(re)re.innerHTML='<option value="">— موظف —</option>'+opts;
    var det=$('#detailEmployeeSelect');if(det)det.innerHTML='<option value="">— اختر موظف —</option>'+opts;
  }catch(e){}
}
async function loadScenarioDepts(){
  try{
    var r=await fetch('/api/departments');
    if(!r.ok)return;
    var depts=await r.json();
    var opts='';
    (depts||[]).forEach(function(d){opts+='<option value="'+(d.name||d)+'">'+(d.name||d)+'</option>'});
    var sd=$('#scenarioDept');if(sd)sd.innerHTML='<option value="">— القسم —</option>'+opts;
  }catch(e){}
}

// ─── PHASE 4: DETAIL ANALYSIS ──────────────────────────────
function getSelectedEmployee(){return parseInt($('#detailEmployeeSelect').value)}
async function showLeaveDetail(){
  var id=getSelectedEmployee();
  if(!id){$('#detailResult').innerHTML='<div style="color:var(--red)">❌ الرجاء اختيار موظف</div>';return}
  $('#detailResult').innerHTML='<div class="spinner" style="margin:0 auto"></div>';
  try{
    var d=await getJSON(API.leaveDetail(id));
    if(!d){$('#detailResult').innerHTML='<div style="color:var(--red)">❌ لا توجد بيانات</div>';return}
    var html='<div class="detail-panel" style="max-width:100%">';
    html+='<div style="display:flex;justify-content:space-between;align-items:center"><h4 style="font-size:15px">📅 تحليل الإجازات — '+d.employee_name+'</h4><button class="btn btn-sm" onclick="$(\'#detailResult\').innerHTML=\'\'" style="background:var(--border2)">✕</button></div>';
    html+='<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;margin:12px 0">';
    html+='<div class="metric-box"><div class="metric-value">'+d.leave_probability_label+'</div><div class="metric-label">المخاطر</div></div>';
    html+='<div class="metric-box"><div class="metric-value">'+(d.leave_probability*100).toFixed(0)+'%</div><div class="metric-label">احتمالية الإجازة</div></div>';
    html+='<div class="metric-box"><div class="metric-value">'+d.total_leaves_history+'</div><div class="metric-label">إجازات سابقة</div></div>';
    html+='<div class="metric-box"><div class="metric-value">'+d.average_duration_days+'</div><div class="metric-label">متوسط الأيام</div></div>';
    html+='</div>';
    if(d.predicted_dates&&d.predicted_dates.length){
      html+='<div class="section-title" style="padding:8px 0"><i class="ti ti-calendar-event"></i> التواريخ المتوقعة</div>';
      d.predicted_dates.forEach(function(p){html+='<div class="stat-row"><span class="stat-label">'+p.date+'</span><span class="stat-value">ثقة: '+(p.confidence*100).toFixed(0)+'%</span></div>'})
    }
    if(d.reasons&&Object.keys(d.reasons).length){
      html+='<div class="section-title" style="padding:8px 0"><i class="ti ti-pie-chart"></i> أسباب الإجازات</div>';
      Object.keys(d.reasons).forEach(function(k){html+='<div class="stat-row"><span class="stat-label">'+k+'</span><span class="stat-value">'+d.reasons[k]+'</span></div>'})
    }
    html+='</div>';
    $('#detailResult').innerHTML=html;
  }catch(e){$('#detailResult').innerHTML='<div style="color:var(--red)">❌ خطأ: '+e.message+'</div>'}
}
async function showAbsenceDetail(){
  var id=getSelectedEmployee();
  if(!id){$('#detailResult').innerHTML='<div style="color:var(--red)">❌ الرجاء اختيار موظف</div>';return}
  $('#detailResult').innerHTML='<div class="spinner" style="margin:0 auto"></div>';
  try{
    var d=await getJSON(API.absenceDetail(id));
    if(!d){$('#detailResult').innerHTML='<div style="color:var(--red)">❌ لا توجد بيانات</div>';return}
    var html='<div class="detail-panel" style="max-width:100%">';
    html+='<div style="display:flex;justify-content:space-between;align-items:center"><h4 style="font-size:15px">🔍 تحليل احتمالية الغياب — '+d.employee_name+'</h4><button class="btn btn-sm" onclick="$(\'#detailResult\').innerHTML=\'\'" style="background:var(--border2)">✕</button></div>';
    html+='<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;margin:12px 0">';
    html+='<div class="metric-box"><div class="metric-value">'+(d.absence_risk*100).toFixed(0)+'%</div><div class="metric-label">احتمالية الغياب</div></div>';
    html+='<div class="metric-box"><div class="metric-value">'+d.risk_level+'</div><div class="metric-label">مستوى المخاطر</div></div>';
    html+='</div>';
    if(d.risk_factors&&d.risk_factors.length){
      html+='<div class="section-title" style="padding:8px 0"><i class="ti ti-list-check"></i> عوامل الخطر</div>';
      d.risk_factors.forEach(function(f){
        var pct=Math.min(f.weight,100);
        var color=pct>20?'#ef4444':pct>10?'#f59e0b':'#6366f1';
        html+='<div class="factor-bar"><span class="bar-label">'+f.factor+'</span><div class="bar-track"><div class="bar-fill" style="width:'+pct+'%;background:'+color+'"></div></div><span class="bar-value" style="color:'+color+'">'+pct+'</span></div>'
      })
    }
    if(d.predicted_absence_days&&d.predicted_absence_days.length){
      html+='<div class="section-title" style="padding:8px 0"><i class="ti ti-calendar-exclamation"></i> الأيام المتوقعة للغياب</div>';
      d.predicted_absence_days.forEach(function(p){html+='<div class="stat-row"><span class="stat-label">'+p.date+'</span><span class="stat-value">احتمالية '+(p.probability*100).toFixed(0)+'%</span></div>'})
    }
    if(d.recommendations&&d.recommendations.length){
      html+='<div class="section-title" style="padding:8px 0"><i class="ti ti-bulb"></i> التوصيات</div>';
      d.recommendations.forEach(function(r){html+='<div class="stat-row"><span class="stat-label" style="color:'+(r.priority==='high'?'var(--red)':'var(--amber)')+'">'+(r.priority==='high'?'🔴':'🟡')+' '+r.text+'</span></div>'})
    }
    html+='</div>';
    $('#detailResult').innerHTML=html;
  }catch(e){$('#detailResult').innerHTML='<div style="color:var(--red)">❌ خطأ: '+e.message+'</div>'}
}
async function showTurnoverDetail(){
  var id=getSelectedEmployee();
  if(!id){$('#detailResult').innerHTML='<div style="color:var(--red)">❌ الرجاء اختيار موظف</div>';return}
  $('#detailResult').innerHTML='<div class="spinner" style="margin:0 auto"></div>';
  try{
    var d=await getJSON(API.turnoverDetail(id));
    if(!d){$('#detailResult').innerHTML='<div style="color:var(--red)">❌ لا توجد بيانات</div>';return}
    var html='<div class="detail-panel" style="max-width:100%">';
    html+='<div style="display:flex;justify-content:space-between;align-items:center"><h4 style="font-size:15px">👤 تحليل مخاطر الرحيل — '+d.employee_name+'</h4><button class="btn btn-sm" onclick="$(\'#detailResult\').innerHTML=\'\'" style="background:var(--border2)">✕</button></div>';
    html+='<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;margin:12px 0">';
    html+='<div class="metric-box"><div class="metric-value" style="color:'+(d.risk_score>0.7?'var(--red)':d.risk_score>0.4?'var(--amber)':'var(--green)')+'">'+(d.risk_score*100).toFixed(0)+'%</div><div class="metric-label">احتمالية الرحيل</div></div>';
    html+='<div class="metric-box"><div class="metric-value" style="color:#8b5cf6">'+(d.model_confidence*100).toFixed(0)+'%</div><div class="metric-label">ثقة النموذج</div></div>';
    html+='<div class="metric-box"><div class="metric-value">'+d.expected_months_before_departure+'</div><div class="metric-label">الأشهر المتوقعة</div></div>';
    html+='</div>';
    if(d.negative_factors&&d.negative_factors.length){
      html+='<div class="section-title" style="padding:8px 0;color:var(--red)"><i class="ti ti-arrow-down-circle"></i> العوامل السلبية (تزيد المخاطر)</div>';
      d.negative_factors.forEach(function(f){html+='<div class="factor-bar"><span class="bar-label">🔴 '+f.factor+'</span><div class="bar-track"><div class="bar-fill" style="width:'+f.weight+'%;background:#ef4444"></div></div><span class="bar-value" style="color:#ef4444">'+f.weight+'%</span></div>'})
    }
    if(d.positive_factors&&d.positive_factors.length){
      html+='<div class="section-title" style="padding:8px 0;color:var(--green)"><i class="ti ti-arrow-up-circle"></i> العوامل الإيجابية (تخفف المخاطر)</div>';
      d.positive_factors.forEach(function(f){html+='<div class="factor-bar"><span class="bar-label">🟢 '+f.factor+'</span><div class="bar-track"><div class="bar-fill" style="width:'+Math.abs(f.weight)+'%;background:#22c55e"></div></div><span class="bar-value" style="color:#22c55e">'+f.weight+'%</span></div>'})
    }
    if(d.recommended_actions&&d.recommended_actions.length){
      html+='<div class="section-title" style="padding:8px 0"><i class="ti ti-checklist"></i> الإجراءات الموصى بها</div>';
      d.recommended_actions.forEach(function(r){
        if(!r)return;
        var ic=r.priority==='عاجل'?'🔴':r.priority==='عالي'?'🟠':'🟢';
        html+='<div class="rec-card info"><span class="rec-icon">'+ic+'</span><div><div class="rec-title">'+r.action+' <span style="color:var(--muted);font-size:11px">('+r.priority+')</span></div><div class="rec-msg">'+r.reason+'</div></div></div>'
      })
    }
    html+='<div style="display:flex;gap:8px;margin-top:12px">';
    html+='<button class="btn btn-accent btn-sm" onclick="window.location.href=\'/admin/employees/'+d.employee_id+'/profile\'"><i class="ti ti-briefcase"></i> خطة الاحتفاظ</button>';
    html+='</div></div>';
    $('#detailResult').innerHTML=html;
  }catch(e){$('#detailResult').innerHTML='<div style="color:var(--red)">❌ خطأ: '+e.message+'</div>'}
}

// ─── PHASE 5: WHAT-IF ──────────────────────────────────────
async function runScenario(){
  var type=$('#scenarioType').value,emp=$('#scenarioEmployee').value,dept=$('#scenarioDept').value,cnt=parseInt($('#scenarioCount').value)||2,pct=parseInt($('#scenarioPct').value)||10;
  var params={};
  if(type==='employee_departure'&&emp)params.employee_id=parseInt(emp);
  if(type==='mass_leave'){if(dept)params.department=dept;params.count=cnt}
  if(type==='budget_cut')params.percentage=pct;
  if(type==='new_hire'){if(dept)params.department=dept;params.count=cnt}
  $('#scenarioResult').innerHTML='<div class="spinner" style="margin:0 auto"></div>';
  try{
    var r=await postJSON(API.simulate,{scenario_type:type,params:params});
    if(r.error){$('#scenarioResult').innerHTML='<div style="color:var(--red)">❌ '+r.error+'</div>';return}
    var html='<div class="scenario-card"><div class="scenario-icon">🧪</div><h4 style="margin-bottom:8px">'+r.scenario+'</h4>';
    var imp=r.impact||r;
    var keys=Object.keys(imp).filter(function(k){return k!=='hiring_cost_lyd'&&k!=='weeks_to_replace'});
    keys.forEach(function(k){
      var label=k.replace(/_/g,' ').replace(/\b\w/g,function(c){return c.toUpperCase()});
      html+='<div class="stat-row"><span class="stat-label">'+label+'</span><span class="stat-value">'+imp[k]+'</span></div>'
    });
    if(imp.hiring_cost_lyd!==undefined)html+='<div class="stat-row"><span class="stat-label">تكلفة التوظيف</span><span class="stat-value">'+imp.hiring_cost_lyd+' د.ل</span></div>';
    html+='<div style="margin-top:8px;padding:8px;background:rgba(16,185,129,.1);border-radius:8px;font-size:13px"><strong>💡 الحل:</strong> '+(r.recommendation||'—')+'</div>';
    html+='</div>';
    $('#scenarioResult').innerHTML=html;
  }catch(e){$('#scenarioResult').innerHTML='<div style="color:var(--red)">❌ خطأ: '+e.message+'</div>'}
}

// ─── PHASE 7: TRENDS ──────────────────────────────────────
async function loadTrends(){
  var grid=$('#trendsGrid');
  grid.innerHTML='';
  try{
    var [leave,absence,turnover,staffing]=await Promise.all([
      getJSON(API.trendsLeave+'?months=12'),
      getJSON(API.trendsAbsence+'?months=6'),
      getJSON(API.trendsTurnover+'?months=12'),
      getJSON(API.trendsStaffing+'?months=6')
    ]);
    // Leave trends
    var lhtml='<div class="ai-card"><div class="card-icon" style="background:#8b5cf622;color:#8b5cf6"><i class="ti ti-calendar-stats"></i></div><h3>اتجاهات الإجازات (12 شهر)</h3>';
    lhtml+=trendBarChart(leave.monthly_leaves||{});
    lhtml+='<div class="stat-row"><span class="stat-label">الإجمالي</span><span class="stat-value">'+leave.total_leaves_in_period+'</span></div>';
    lhtml+='<div class="stat-row"><span class="stat-label">المعدل الشهري</span><span class="stat-value">'+leave.average_monthly+'</span></div></div>';
    grid.insertAdjacentHTML('beforeend',lhtml);
    // Absence trends
    var ahtml='<div class="ai-card"><div class="card-icon" style="background:#f59e0b22;color:#f59e0b"><i class="ti ti-user-x"></i></div><h3>اتجاهات الغياب (6 أشهر)</h3>';
    ahtml+=trendBarChart(absence.monthly_absences||{});
    ahtml+='<div class="stat-row"><span class="stat-label">الإجمالي</span><span class="stat-value">'+absence.total_absences+'</span></div>';
    ahtml+='<div class="stat-row"><span class="stat-label">أسوأ يوم</span><span class="stat-value">'+absence.worst_day+'</span></div></div>';
    grid.insertAdjacentHTML('beforeend',ahtml);
    // Turnover trends
    var thtml='<div class="ai-card"><div class="card-icon" style="background:#ec489922;color:#ec4899"><i class="ti ti-users-x"></i></div><h3>اتجاهات الدوران الوظيفي</h3>';
    thtml+='<div class="stat-row"><span class="stat-label">المعدل التاريخي</span><span class="stat-value">'+turnover.historical_turnover_rate+'%</span></div>';
    thtml+='<div class="stat-row"><span class="stat-label">المعرضون حالياً</span><span class="stat-value">'+turnover.current_at_risk+'</span></div>';
    thtml+='<div class="stat-row"><span class="stat-label">خطورة عالية</span><span class="stat-value">'+turnover.high_risk+'</span></div></div>';
    grid.insertAdjacentHTML('beforeend',thtml);
    // Staffing trends
    var shtml='<div class="ai-card"><div class="card-icon" style="background:#10b98122;color:#10b981"><i class="ti ti-building"></i></div><h3>اتجاهات التغطية (6 أشهر)</h3>';
    if(staffing.monthly_coverage){
      shtml+=trendBarChart(staffing.monthly_coverage.reduce(function(a,c){a[c.month]=c.coverage_pct;return a},{}),'#10b981');
    }
    shtml+='<div class="stat-row"><span class="stat-label">متوسط التغطية</span><span class="stat-value">'+staffing.average_coverage+'%</span></div></div>';
    grid.insertAdjacentHTML('beforeend',shtml);
  }catch(e){grid.innerHTML='<div class="ai-card" style="grid-column:1/-1;text-align:center;padding:40px;color:var(--red)">❌ خطأ في تحميل الاتجاهات</div>'}
}
function trendBarChart(data,color){
  var keys=Object.keys(data||{}).slice(-12);
  if(!keys.length)return'<div style="color:var(--muted);font-size:12px;padding:8px 0">لا توجد بيانات كافية</div>';
  var maxV=Math.max.apply(null,keys.map(function(k){return data[k]}),1);
  var barC=color||'#8b5cf6';
  var html='<div class="trend-mini-chart">';
  keys.forEach(function(k){
    var h=Math.max(2,(data[k]/maxV)*70);
    html+='<div class="trend-bar" style="height:'+h+'px;background:'+barC+';opacity:'+(0.4+0.6*(data[k]/maxV))+'" title="'+k+': '+data[k]+'"></div>'
  });
  html+='</div><div style="display:flex;justify-content:space-between;font-size:9px;color:var(--muted2)">';
  html+='<span>'+keys[0]+'</span><span>'+keys[keys.length-1]+'</span></div>';
  return html;
}

// ─── PHASE 8: LIVE STATUS ─────────────────────────────────
async function loadLiveStatus(){
  var grid=$('#liveGrid');
  try{
    var d=await getJSON(API.liveStatus);
    var html='<div class="ai-card" style="grid-column:1/-1"><div class="card-icon" style="background:'+(d.status==='good'?'#22c55e':d.status==='warning'?'#f59e0b':'#ef4444')+'22;color:'+(d.status==='good'?'#22c55e':d.status==='warning'?'#f59e0b':'#ef4444')+'"><i class="ti ti-monitor"></i></div><h3>🔴 المراقبة المباشرة <span class="live-indicator '+(d.status||'online')+'" style="display:inline-block;vertical-align:middle"></span></h3>';
    html+='<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px;margin:10px 0">';
    html+='<div class="metric-box"><div class="metric-value" style="color:#22c55e">'+d.available+'</div><div class="metric-label">متاح الآن</div></div>';
    html+='<div class="metric-box"><div class="metric-value" style="color:#8b5cf6">'+d.total_employees+'</div><div class="metric-label">إجمالي الموظفين</div></div>';
    html+='<div class="metric-box"><div class="metric-value" style="color:var(--amber)">'+d.on_leave+'</div><div class="metric-label">في إجازة</div></div>';
    html+='<div class="metric-box"><div class="metric-value" style="color:var(--red)">'+d.absent+'</div><div class="metric-label">غائب</div></div>';
    html+='<div class="metric-box"><div class="metric-value" style="color:'+(d.status==='good'?'#22c55e':d.status==='warning'?'#f59e0b':'#ef4444')+'">'+d.coverage_pct+'%</div><div class="metric-label">التغطية</div></div>';
    html+='</div>';
    if(d.alerts&&d.alerts.length){
      html+='<div class="section-title" style="padding:8px 0"><i class="ti ti-alert-triangle"></i> التنبيهات النشطة</div>';
      d.alerts.forEach(function(a){html+='<div class="rec-card '+(a.type==='critical'?'critical':'warning')+'"><span class="rec-icon">'+(a.type==='critical'?'🔴':'🟡')+'</span><div><div class="rec-msg">'+a.message+'</div></div></div>'})
    }
    if(d.departments&&d.departments.length){
      html+='<div class="section-title" style="padding:8px 0"><i class="ti ti-building-community"></i> حالة الأقسام</div>';
      d.departments.forEach(function(dp){
        var ic=dp.status==='good'?'🟢':dp.status==='warning'?'🟡':'🔴';
        html+='<div class="stat-row clickable"><span class="stat-label">'+ic+' '+dp.department+'</span><span class="stat-value">'+dp.available+'/'+dp.total+' متاح</span></div>'
      })
    }
    html+='</div>';
    grid.innerHTML=html;
    setTimeout(loadLiveStatus,30000);
  }catch(e){grid.innerHTML='<div class="ai-card" style="grid-column:1/-1;text-align:center;padding:40px;color:var(--red)">❌ خطأ في التحميل</div>'}
}

// ─── PHASE 9: REPORTS ──────────────────────────────────────
async function previewReport(){
  var type=$('#reportType').value,emp=$('#reportEmployee').value;
  var url=API.reportData+'?type='+type+(emp?'&employee_id='+emp:'');
  $('#reportResult').innerHTML='<div class="spinner" style="margin:0 auto"></div>';
  var csvUrl=API.reportCSV+'?type='+type+(emp?'&employee_id='+emp:'');
  var link=$('#csvDownloadLink');
  link.href=csvUrl;
  link.style.display='inline-flex';
  try{
    var d=await getJSON(url);
    if(!d){$('#reportResult').innerHTML='<div style="color:var(--red)">❌ لا توجد بيانات</div>';return}
    var html='<div class="scenario-card"><h4 style="margin-bottom:6px">📄 '+d.title+'</h4><div style="color:var(--muted);font-size:12px;margin-bottom:8px">'+d.date+'</div>';
    (d.sections||[]).forEach(function(s){
      html+='<div class="section-title" style="padding:4px 0;font-size:12px">'+s.heading+'</div>';
      (s.rows||[]).forEach(function(r){
        if(!Array.isArray(r))return;
        html+='<div class="stat-row"><span class="stat-label">'+r[0]+'</span><span class="stat-value">'+(r[1]??'—')+'</span></div>'
      })
    });
    html+='</div>';
    $('#reportResult').innerHTML=html;
  }catch(e){$('#reportResult').innerHTML='<div style="color:var(--red)">❌ خطأ: '+e.message+'</div>'}
}

// ─── PHASE 10: MODEL PERFORMANCE ───────────────────────────
async function loadModelPerformance(){
  var grid=$('#modelsGrid');
  try{
    var models=await getJSON(API.modelPerf);
    var html='<div class="ai-card" style="grid-column:1/-1"><div class="card-icon" style="background:#8b5cf622;color:#8b5cf6"><i class="ti ti-brain"></i></div><h3>🤖 أداء نماذج AI</h3>';
    html+='<table class="perf-table"><thead><tr><th>النموذج</th><th>النوع</th><th>الدقة</th><th>الضبط</th><th>الاستدعاء</th><th>F1</th><th>آخر تحديث</th></tr></thead><tbody>';
    Object.keys(models).forEach(function(k){
      var m=models[k];
      html+='<tr><td style="text-align:right;font-weight:600">'+m.name+'</td><td style="font-size:10px;color:var(--muted)">'+(m.model_type||'—')+'</td>';
      html+='<td><span style="color:'+(m.accuracy_pct>=85?'#22c55e':m.accuracy_pct>=70?'#f59e0b':'#ef4444')+'">'+m.accuracy_pct+'%</span></td>';
      html+='<td>'+m.precision_pct+'%</td><td>'+m.recall_pct+'%</td><td>'+m.f1_pct+'%</td>';
      html+='<td style="font-size:11px;color:var(--muted)">'+(m.last_update||'—')+'</td></tr>'
    });
    html+='</tbody></table></div>';
    grid.innerHTML=html;
  }catch(e){grid.innerHTML='<div class="ai-card" style="grid-column:1/-1;text-align:center;padding:40px;color:var(--red)">❌ خطأ في تحميل أداء النماذج</div>'}
}
