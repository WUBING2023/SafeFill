var polling=null, suggestionAction="";

function updateStatus(){
  fetch("/api/status").then(r=>r.json()).then(d=>{
    var a=d.api||{}, v=d.vault||{}, inf=d.input_forms||{}, nf=d.new_forms||{}, rr=d.review_results||{}, fo=d.final_outputs||{};
    document.getElementById("b-api").textContent="API: "+(a.enabled?"Enabled":"Disabled");
    document.getElementById("b-vault").textContent="Vault: "+v.label;
    document.getElementById("si1").textContent="Old forms: "+(inf.count||0)+" files "+v.label;
    document.getElementById("si2").textContent="New forms: "+(nf.count||0)+" files "+(nf.latest||"");
    document.getElementById("si3").textContent="API: "+(a.enabled?"Enabled":"Disabled")+" | Reviews: "+(rr.count||0);
    document.getElementById("si4").textContent="Reviews: "+(rr.latest||"none")+" | Final: "+(fo.count||0)+" files";
    document.getElementById("si5").textContent="Clean temp files after confirming final output";

    var phase="", sg="", btn="", sa="";
    if(!v.exists){
      phase="Prepare vault"; sg="<p>Put old forms in input_forms, then click <b>Extract Profile</b>.</p>"; sa="profile_extract"; btn="Extract Profile";
    }else if(nf.count==0){
      phase="Awaiting forms"; sg="<p>Put .docx / .xlsx files in new_forms.</p>"; sa=""; btn="";
    }else if(rr.count==0){
      phase="Fill & Review"; sg="<p>Click <b>Fill & Review</b>. API may be used. Browser auto-opens for review.</p>"; sa="form_review"; btn="Fill & Review";
    }else if(fo.count==0 || (rr.latest && fo.latest && rr.latest>fo.latest)){
      phase="Export ready"; sg="<p>Review saved. Click <b>Export Final</b>.</p>"; sa="final_export"; btn="Export Final";
    }else{
      phase="Completed"; sg="<p>Final files ready. Optionally <b>Preview Cleanup</b>.</p>"; sa="cleaner_preview"; btn="Preview Cleanup";
    }
    document.getElementById("b-phase").textContent=phase;
    document.getElementById("sg-content").innerHTML=sg;
    if(btn){document.getElementById("sg-btn").style.display="block";document.getElementById("sg-btn").textContent=btn;suggestionAction=sa}
    else{document.getElementById("sg-btn").style.display="none";suggestionAction=""}
  });
}
function runSuggestion(){if(suggestionAction)run(suggestionAction)}
function run(action){
  if(action=="form_review"&&!confirm("This may call the API and send data to your model provider. Continue?"))return;
  document.getElementById("log-panel").style.display="block";
  document.getElementById("log-title").textContent="Running: "+action;
  document.getElementById("log-output").textContent="Waiting...";
  fetch("/api/run",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:action})})
  .then(r=>r.json()).then(d=>{
    if(d.error){document.getElementById("log-output").textContent="Error: "+d.error;return}
    document.getElementById("log-title").textContent="Running: "+action+" ("+d.job_id+")";
    polling=setInterval(function(){
      fetch("/api/job?id="+d.job_id).then(r=>r.json()).then(j=>{
        document.getElementById("log-output").textContent=j.output||"waiting...";
        if(j.status!="running"){clearInterval(polling);polling=null;document.getElementById("log-title").textContent=j.status+" - "+action;updateStatus()}
      });
    },1000);
  });
}

// -------------------------------------------------------
// ProfileSave conflict detection + modal flow
// -------------------------------------------------------
function saveProfile(){
  document.getElementById("log-panel").style.display="block";
  document.getElementById("log-title").textContent="Detecting conflicts...";
  document.getElementById("log-output").textContent="Checking vault vs new extraction...";

  fetch("/api/profile-save-detect",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"})
  .then(r=>r.json()).then(d=>{
    if(d.status=="error"){
      document.getElementById("log-output").textContent="Detection error: "+(d.message||"unknown");
      return;
    }
    if(d.status=="empty" || d.vault_exists===false){
      // No vault yet -- ask whether to create
      document.getElementById("log-output").textContent="No vault/profile.json yet. Click Save to create.";
      if(confirm("No vault/profile.json exists yet. Create it with the latest extracted data?")){
        run("profile_save_replace");
      }
      return;
    }
    if(d.status=="same"){
      document.getElementById("log-output").textContent="All fields match vault. No changes needed.";
      updateStatus();
      return;
    }
    // Conflict detected -- show modal
    showConflictModal(d);
  }).catch(function(e){
    document.getElementById("log-output").textContent="Detection failed: "+e;
  });
}

function showConflictModal(d){
  var existing=d.existing_name||"?";
  var newer=d.new_name||"?";
  var hasName=d.has_name_conflict;

  var html="";
  html+="<p><b>Vault conflict detected.</b></p>";
  if(hasName){
    html+="<p>Current vault: <b>"+esc(existing)+"</b><br>New extraction: <b>"+esc(newer)+"</b></p>";
    html+="<p style='color:#e65100'>Names differ. SafeFill supports only one vault profile.</p>";
  }

  if(d.conflicts&&d.conflicts.length>0){
    html+="<h4>Conflicts ("+d.conflicts.length+")</h4><table><tr><th>Field</th><th>Vault</th><th>New</th></tr>";
    d.conflicts.forEach(function(c){
      html+="<tr><td>"+esc(c.label)+"</td><td>"+esc(c.old)+"</td><td>"+esc(c.new)+"</td></tr>";
    });
    html+="</table>";
  }
  if(d.can_fill&&d.can_fill.length>0){
    html+="<h4>Can Fill ("+d.can_fill.length+")</h4><table><tr><th>Field</th><th>New Value</th></tr>";
    d.can_fill.forEach(function(c){
      html+="<tr><td>"+esc(c.label)+"</td><td>"+esc(c.value)+"</td></tr>";
    });
    html+="</table>";
  }
  if(d.new_customs&&d.new_customs.length>0){
    html+="<h4>New Custom Fields ("+d.new_customs.length+")</h4><table><tr><th>Field</th><th>Value</th></tr>";
    d.new_customs.forEach(function(c){
      html+="<tr><td>"+esc(c.label)+"</td><td>"+esc(c.value)+"</td></tr>";
    });
    html+="</table>";
  }
  html+="<p style='color:#e65100;font-size:13px'>Replacing will backup the current profile.json first.</p>";

  document.getElementById("modal-body").innerHTML=html;
  document.getElementById("modal-overlay").style.display="flex";

  // Store data for button handlers
  window._detectData=d;
}

function closeModal(){
  document.getElementById("modal-overlay").style.display="none";
}

function doReplace(){
  closeModal();
  if(!confirm("This will REPLACE the current vault/profile.json with the new extraction. A backup will be made first. Confirm?"))return;
  run("profile_save_replace");
}

function doFillEmpty(){
  closeModal();
  run("profile_save_fill_empty");
}

function doStop(){
  closeModal();
  document.getElementById("log-output").textContent="Save cancelled. Vault unchanged.";
  updateStatus();
}

function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

updateStatus();setInterval(updateStatus,10000);
