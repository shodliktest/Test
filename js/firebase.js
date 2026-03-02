/* ================================================================
   TestPro 2.0 — firebase.js  (UPDATED: file-based questions + caching)
   ================================================================ */

const firebaseConfig = {
  apiKey:            "AIzaSyD41LIwGEcnVDmsFU73mj12ruoz2s3jdgw",
  authDomain:        "karoke-pro.firebaseapp.com",
  projectId:         "karoke-pro",
  storageBucket:     "karoke-pro.firebasestorage.app",
  messagingSenderId: "696087699873",
  appId:             "1:696087699873:web:81f18119449f25cbceabe0"
};

if (!firebase.apps.length) firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();
const db   = firebase.firestore();

/* Navigation */
const BASE_PATH = (() => {
  const p = window.location.pathname;
  return p.substring(0, p.lastIndexOf('/') + 1);
})();
function goTo(page) { window.location.href = BASE_PATH + page; }

/* Auth */
const AuthHelpers = {
  getCurrentUser() {
    return new Promise((res, rej) => {
      const u = auth.onAuthStateChanged(user => { u(); res(user); }, rej);
    });
  },
  async requireAuth(fallback = 'login.html') {
    const user = await this.getCurrentUser();
    if (!user) { goTo(fallback); return null; }
    return user;
  }
};

/* Subject map */
const SUBJECTS = {
  english:  { label: 'English',     emoji: '🇬🇧' },
  arabic:   { label: 'Arabcha',     emoji: '🕌'  },
  russian:  { label: 'Ruscha',      emoji: '🇷🇺' },
  turkish:  { label: 'Turkcha',     emoji: '🇹🇷' },
  math:     { label: 'Matematika',  emoji: '🧮'  },
  it:       { label: 'IT / CS',     emoji: '💻'  },
  science:  { label: 'Fanlar',      emoji: '🔬'  },
  religion: { label: 'Din',         emoji: '📖'  },
  other:    { label: 'Boshqa',      emoji: '📚'  },
};
function getSubject(k) { return SUBJECTS[k] || { label: k || 'Boshqa', emoji: '📚' }; }

/* Helpers */
function esc(s) {
  const d = document.createElement('div');
  d.textContent = String(s || '');
  return d.innerHTML;
}
function fmtDate(ts) {
  if (!ts) return '—';
  try {
    const d = ts.toDate ? ts.toDate() : new Date(ts.seconds ? ts.seconds * 1000 : ts);
    return d.toLocaleDateString('uz-UZ', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return '—'; }
}
function fmtTime(secs) {
  secs = secs || 0;
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0');
}
function randCode(n = 6) {
  const c = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  return Array.from({length:n}, () => c[Math.floor(Math.random()*c.length)]).join('');
}

/* LocalStorage Cache */
const Cache = {
  _key(testId) { return 'tp_test_' + testId; },
  _ansKey(testId) { return 'tp_answers_' + testId; },
  saveTest(testId, testData, questions) {
    try {
      localStorage.setItem(this._key(testId), JSON.stringify({ testData, questions, savedAt: Date.now() }));
    } catch(e) { console.warn('Cache save error:', e); }
  },
  loadTest(testId) {
    try {
      const raw = localStorage.getItem(this._key(testId));
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  },
  clearTest(testId) {
    localStorage.removeItem(this._key(testId));
    localStorage.removeItem(this._ansKey(testId));
  },
  saveAnswers(testId, answers) {
    try { localStorage.setItem(this._ansKey(testId), JSON.stringify(answers)); } catch(e) {}
  },
  loadAnswers(testId) {
    try {
      const raw = localStorage.getItem(this._ansKey(testId));
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  }
};

/* DB */
const DB = {
  async getUser(uid) {
    try {
      const d = await db.collection('users').doc(uid).get();
      return d.exists ? { id: d.id, ...d.data() } : null;
    } catch(e) { console.warn('getUser:', e.message); return null; }
  },
  async createUser(uid, data) {
    await db.collection('users').doc(uid).set({
      ...data, role: 'user', createdAt: firebase.firestore.FieldValue.serverTimestamp()
    });
  },
  async updateUser(uid, data) {
    await db.collection('users').doc(uid).set(
      { ...data, updatedAt: firebase.firestore.FieldValue.serverTimestamp() }, { merge: true }
    );
  },
  async getAllUsers() {
    const snap = await db.collection('users').get();
    return snap.docs.map(d => ({ id: d.id, ...d.data() }))
      .sort((a,b) => (b.createdAt?.seconds||0) - (a.createdAt?.seconds||0));
  },

  async getTest(id) {
    const d = await db.collection('tests').doc(id).get();
    return d.exists ? { id: d.id, ...d.data() } : null;
  },
  async getMyTests(authorId) {
    const snap = await db.collection('tests').where('authorId', '==', authorId).get();
    const list = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    return list.sort((a,b) => (b.createdAt?.seconds||0) - (a.createdAt?.seconds||0));
  },
  async getPublicTests() {
    const snap = await db.collection('tests').where('visibility', '==', 'public').get();
    const list = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    return list.sort((a,b) => (b.createdAt?.seconds||0) - (a.createdAt?.seconds||0));
  },
  async getAllTests() {
    const snap = await db.collection('tests').get();
    const list = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    return list.sort((a,b) => (b.createdAt?.seconds||0) - (a.createdAt?.seconds||0));
  },
  async getTestByCode(code) {
    const snap = await db.collection('tests')
      .where('accessCode', '==', code.toUpperCase().trim()).get();
    if (snap.empty) return null;
    const d = snap.docs[0];
    return { id: d.id, ...d.data() };
  },
  async createTest(data, authorId) {
    const code = data.accessCode || randCode(6);
    const ref = await db.collection('tests').add({
      ...data, accessCode: code, authorId, attempts: 0, averageScore: 0,
      createdAt: firebase.firestore.FieldValue.serverTimestamp(),
      updatedAt: firebase.firestore.FieldValue.serverTimestamp(),
    });
    return { id: ref.id, accessCode: code };
  },
  async updateTest(id, data) {
    await db.collection('tests').doc(id).update({
      ...data, updatedAt: firebase.firestore.FieldValue.serverTimestamp()
    });
  },
  async deleteTest(id) {
    Cache.clearTest(id);
    await db.collection('test_questions').doc(id).delete().catch(()=>{});
    await db.collection('tests').doc(id).delete();
  },

  /* QUESTIONS — bitta fayl sifatida */
  async getQuestions(testId) {
    const doc = await db.collection('test_questions').doc(testId).get();
    if (doc.exists) {
      return (doc.data().questions || []).sort((a,b) => (a.order||0) - (b.order||0));
    }
    // backward compat: subcollection
    const snap = await db.collection('tests').doc(testId).collection('questions').get();
    return snap.docs.map(d => ({ id: d.id, ...d.data() }))
      .sort((a,b) => (a.order||0) - (b.order||0));
  },

  async getTestWithQuestions(testId) {
    const cached = Cache.loadTest(testId);
    if (cached && cached.questions) {
      return { testData: cached.testData, questions: cached.questions };
    }
    const [testData, questions] = await Promise.all([
      this.getTest(testId), this.getQuestions(testId)
    ]);
    if (testData) Cache.saveTest(testId, testData, questions);
    return { testData, questions };
  },

  async saveQuestions(testId, questions) {
    const clean = questions.map((q, i) => {
      const { id: _id, ...c } = q;
      return {
        ...c, order: i,
        text:        c.text        || '',
        type:        c.type        || 'multiple',
        options:     c.options     || [],
        correct:     c.correct     ?? 0,
        correctOrder: c.correctOrder || [],
        blanks:      c.blanks      || [],
        explanation: c.explanation || '',
        points:      c.points      || 1,
      };
    });
    await db.collection('test_questions').doc(testId).set({
      questions: clean,
      questionCount: questions.length,
      updatedAt: firebase.firestore.FieldValue.serverTimestamp()
    });
    await db.collection('tests').doc(testId).update({ questionCount: questions.length });
    const testData = await this.getTest(testId);
    if (testData) Cache.saveTest(testId, testData, clean);
  },

  /* RESULTS — hammasi localStorage da, Firebase ga yozilmaydi */
  async saveResult(data) {
    try {
      const key = 'tp_results';
      const existing = JSON.parse(localStorage.getItem(key) || '[]');
      const result = {
        ...data,
        id: 'r_' + Date.now(),
        completedAt: Date.now(),
      };
      existing.unshift(result);
      if (existing.length > 100) existing.splice(100);
      localStorage.setItem(key, JSON.stringify(existing));
      return result.id;
    } catch(e) {
      console.warn('saveResult localStorage:', e);
      return null;
    }
  },

  async getMyResults(userId, limit = 20) {
    try {
      const all = JSON.parse(localStorage.getItem('tp_results') || '[]');
      const mine = userId ? all.filter(r => r.userId === userId) : all;
      return limit ? mine.slice(0, limit) : mine;
    } catch { return []; }
  }
};

window.auth = auth; window.db = db; window.DB = DB; window.Cache = Cache;
window.AuthHelpers = AuthHelpers; window.SUBJECTS = SUBJECTS; window.getSubject = getSubject;
window.esc = esc; window.fmtDate = fmtDate; window.fmtTime = fmtTime;
window.randCode = randCode; window.goTo = goTo;
