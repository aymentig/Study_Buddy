const drop = document.getElementById('drop');
const fileInput = document.getElementById('file');
const progress = document.getElementById('progress');
const bar = progress.querySelector('.bar');
const pct = progress.querySelector('.pct');

const summaryCard = document.getElementById('summary-card');
const keypointsCard = document.getElementById('keypoints-card');
const quizCard = document.getElementById('quiz-card');
const planCard = document.getElementById('plan-card');

const summaryEl = document.getElementById('summary');
const kpsEl = document.getElementById('keypoints');
const quizEl = document.getElementById('quiz');
const planEl = document.getElementById('plan');

function setProgress(v){
  progress.hidden = false;
  bar.style.width = `${v}%`;
  pct.textContent = `${v}%`;
}

function finishProgress(){
  setProgress(100);
  setTimeout(() => { progress.hidden = true; setProgress(0); }, 600);
}

function preventDefaults(e){
  e.preventDefault();
  e.stopPropagation();
}
['dragenter','dragover','dragleave','drop'].forEach(ev => {
  drop.addEventListener(ev, preventDefaults, false);
});
['dragenter','dragover'].forEach(ev => {
  drop.addEventListener(ev, () => drop.classList.add('hover'), false);
});
['dragleave','drop'].forEach(ev => {
  drop.addEventListener(ev, () => drop.classList.remove('hover'), false);
});

drop.addEventListener('drop', (e) => {
  const dt = e.dataTransfer;
  const f = dt.files && dt.files[0];
  if (f) upload(f);
});

fileInput.addEventListener('change', (e) => {
  const f = e.target.files[0];
  if (f) upload(f);
});

async function upload(file){
  // basic validation
  const ok = ['pdf','docx','txt'].some(ext => file.name.toLowerCase().endsWith('.' + ext));
  if(!ok){ alert('Please upload a PDF, DOCX, or TXT.'); return; }

  // fake client-side progress to feel responsive
  let fake = 0; setProgress(fake);
  const tick = setInterval(() => { fake = Math.min(fake+7, 85); setProgress(fake); }, 120);

  try{
    const fd = new FormData();
    fd.append('file', file);

    const res = await fetch('/api/analyze', { method:'POST', body: fd });
    const json = await res.json();

    clearInterval(tick);
    finishProgress();

    if(!res.ok){
      alert(json.error || 'Something went wrong.');
      return;
    }
    renderResults(json);
  }catch(err){
    clearInterval(tick);
    finishProgress();
    alert('Network error: ' + err.message);
  }
}

function renderResults(data){
  // Summary
  summaryEl.textContent = data.summary || 'No summary generated.';
  summaryCard.hidden = false;

  // Key points
  kpsEl.innerHTML = '';
  (data.keyPoints || []).forEach(k => {
    const li = document.createElement('li'); li.textContent = k; kpsEl.appendChild(li);
  });
  keypointsCard.hidden = false;

  // Quiz
  quizEl.innerHTML = '';
  (data.quizQuestions || []).forEach((q, idx) => {
    const wrap = document.createElement('div');
    wrap.className = 'qa';
    const title = document.createElement('div');
    title.innerHTML = `<strong>Q${idx+1}.</strong> ${q.question}`;
    wrap.appendChild(title);

    const list = document.createElement('ul');
    list.style.margin = '8px 0 0 0';
    list.style.paddingLeft = '18px';

    (q.options || []).forEach((opt, i) => {
      const li = document.createElement('li');
      li.textContent = String.fromCharCode(65+i) + '. ' + opt;
      list.appendChild(li);
    });
    wrap.appendChild(list);

    const ans = document.createElement('div');
    ans.className = 'answers';
    const btn = document.createElement('button');
    btn.textContent = 'Reveal answer';
    btn.className = 'btn';
    const answerText = document.createElement('span');
    answerText.style.marginLeft = '8px';
    answerText.style.display = 'none';
    const correctIdx = typeof q.correct === 'number' ? q.correct : -1;
    answerText.textContent = correctIdx >= 0 ? `Correct: ${String.fromCharCode(65+correctIdx)}` : 'No answer provided';
    btn.onclick = () => {
      answerText.style.display = answerText.style.display === 'none' ? 'inline' : 'none';
    };
    ans.appendChild(btn); ans.appendChild(answerText);
    wrap.appendChild(ans);

    quizEl.appendChild(wrap);
  });
  quizCard.hidden = false;

  // Study Plan
  planEl.innerHTML = '';
  (data.studyGuide || []).forEach(p => {
    const li = document.createElement('li'); li.textContent = p; planEl.appendChild(li);
  });
  planCard.hidden = false;

  // scroll into view on first render
  summaryCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
