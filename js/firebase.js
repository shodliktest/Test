/* ================================================================
   TestPro 2.0 — firebase.js  (COMPLETE & CLEAN)
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

/* ── Navigation ── */
const BASE_PATH = (() => {
  const p = window.location.pathname;
  return p.substring(0, p.lastIndexOf('/') + 1);
})();
function goTo(page) { window.location.href = BASE_PATH + page; }

/* ── Auth ── */
const AuthHelpers = {
  getCurrentUser() {
    // Telegram WebView va ba'zi brauzerlarda onAuthStateChanged hang bo'lishi mumkin
    // 4 soniya timeout bilan — agar auth ishlamasa null qaytaramiz
    return new Promise((res) => {
      let done = false;
      const timer = setTimeout(() => {
        if (!done) { done = true; res(null); }
      }, 4000);
      const unsub = auth.onAuthStateChanged(user => {
        if (!done) {
          done = true;
          clearTimeout(timer);
          unsub();
          res(user);
        }
      }, () => {
        if (!done) { done = true; clearTimeout(timer); res(null); }
      });
    });
  },
  async requireAuth(fallback = 'login.html') {
    const user = await this.getCurrentUser();
    if (!user) { goTo(fallback); return null; }
    return user;
  }
};

/* ── Subject map ── */
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
function getSubject(k) {
  return SUBJECTS[k] || { label: k || 'Boshqa', emoji: '📚' };
}

/* ── Helpers ── */
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

/* ── DB ── */
const DB = {

  /* ── USERS ── */
  async getUser(uid) {
    try {
      const d = await db.collection('users').doc(uid).get();
      return d.exists ? { id: d.id, ...d.data() } : null;
    } catch(e) { console.warn('getUser:', e.message); return null; }
  },
  async createUser(uid, data) {
    await db.collection('users').doc(uid).set({
      ...data,
      role: 'user',
      createdAt: firebase.firestore.FieldValue.serverTimestamp()
    });
  },
  async updateUser(uid, data) {
    await db.collection('users').doc(uid).set(
      { ...data, updatedAt: firebase.firestore.FieldValue.serverTimestamp() },
      { merge: true }
    );
  },
  async getAllUsers() {
    const snap = await db.collection('users').get();
    return snap.docs.map(d => ({ id: d.id, ...d.data() }))
      .sort((a,b) => (b.createdAt?.seconds||0) - (a.createdAt?.seconds||0));
  },

  /* ── TESTS ── */
  async getTest(id) {
    const d = await db.collection('tests').doc(id).get();
    return d.exists ? { id: d.id, ...d.data() } : null;
  },

  // Mening testlarim — faqat authorId filteri (index shart emas)
  async getMyTests(authorId) {
    const snap = await db.collection('tests')
      .where('authorId', '==', authorId)
      .get();
    const list = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    return list.sort((a,b) => (b.createdAt?.seconds||0) - (a.createdAt?.seconds||0));
  },

  // Ommaviy testlar
  async getPublicTests() {
    const snap = await db.collection('tests')
      .where('visibility', '==', 'public')
      .get();
    const list = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    return list.sort((a,b) => (b.createdAt?.seconds||0) - (a.createdAt?.seconds||0));
  },

  // Admin: barcha testlar
  async getAllTests() {
    const snap = await db.collection('tests').get();
    const list = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    return list.sort((a,b) => (b.createdAt?.seconds||0) - (a.createdAt?.seconds||0));
  },

  // Kod orqali
  async getTestByCode(code) {
    const snap = await db.collection('tests')
      .where('accessCode', '==', code.toUpperCase().trim())
      .get();
    if (snap.empty) return null;
    const d = snap.docs[0];
    return { id: d.id, ...d.data() };
  },

  async createTest(data, authorId) {
    const code = data.accessCode || randCode(6);
    const ref = await db.collection('tests').add({
      ...data,
      accessCode:   code,
      authorId:     authorId,
      attempts:     0,
      averageScore: 0,
      createdAt:    firebase.firestore.FieldValue.serverTimestamp(),
      updatedAt:    firebase.firestore.FieldValue.serverTimestamp(),
    });
    return { id: ref.id, accessCode: code };
  },

  async updateTest(id, data) {
    await db.collection('tests').doc(id).update({
      ...data,
      updatedAt: firebase.firestore.FieldValue.serverTimestamp()
    });
  },

  async deleteTest(id) {
    const qs = await db.collection('tests').doc(id).collection('questions').get();
    if (qs.size > 0) {
      const b = db.batch();
      qs.forEach(d => b.delete(d.ref));
      await b.commit();
    }
    await db.collection('tests').doc(id).delete();
  },

  /* ── QUESTIONS ── */
  async getQuestions(testId) {
    const snap = await db.collection('tests').doc(testId).collection('questions').get();
    return snap.docs.map(d => ({ id: d.id, ...d.data() }))
      .sort((a,b) => (a.order||0) - (b.order||0));
  },

  async saveQuestions(testId, questions) {
    const col = db.collection('tests').doc(testId).collection('questions');
    const existing = await col.get();
    if (existing.size > 0) {
      const b = db.batch(); existing.forEach(d => b.delete(d.ref)); await b.commit();
    }
    if (!questions.length) return;
    for (let i = 0; i < questions.length; i += 400) {
      const b = db.batch();
      questions.slice(i, i+400).forEach((q, j) => {
        const { id: _id, ...clean } = q;
        b.set(col.doc(), {
          ...clean,
          order:         i + j,
          text:          clean.text          || '',
          type:          clean.type          || 'multiple',
          options:       clean.options       || [],
          correct:       clean.correct       ?? 0,
          correctAnswer: clean.correctAnswer || '',
          pairs:         clean.pairs         || [],
          words:         clean.words         || [],
          explanation:   clean.explanation   || '',
          points:        clean.points        || 1,
        });
      });
      await b.commit();
    }
    await db.collection('tests').doc(testId).update({ questionCount: questions.length });
  },

  /* ── RESULTS ── */
  async saveResult(data) {
    const ref = await db.collection('results').add({
      ...data,
      completedAt: firebase.firestore.FieldValue.serverTimestamp()
    });
    try {
      const tRef = db.collection('tests').doc(data.testId);
      const td = await tRef.get();
      if (td.exists) {
        const prev = td.data();
        const n = (prev.attempts||0) + 1;
        const avg = Math.round(((prev.averageScore||0) * (prev.attempts||0) + (data.score||0)) / n);
        await tRef.update({ attempts: n, averageScore: avg });
      }
    } catch(e) { console.warn('result stats:', e.message); }
    return ref.id;
  },

  async getMyResults(userId, limit = 20) {
    const snap = await db.collection('results').where('userId', '==', userId).get();
    const list = snap.docs.map(d => ({ id: d.id, ...d.data() }))
      .sort((a,b) => (b.completedAt?.seconds||0) - (a.completedAt?.seconds||0));
    return limit ? list.slice(0, limit) : list;
  }
};

/* ── Globals ── */
window.auth        = auth;
window.db          = db;
window.DB          = DB;
window.AuthHelpers = AuthHelpers;
window.SUBJECTS    = SUBJECTS;
window.getSubject  = getSubject;
window.esc         = esc;
window.fmtDate     = fmtDate;
window.fmtTime     = fmtTime;
window.randCode    = randCode;
window.goTo        = goTo;
