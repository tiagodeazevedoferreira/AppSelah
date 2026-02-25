import { useState, useEffect } from 'react';
import { db } from './firebase';
import { ref, onValue } from 'firebase/database';
import './App.css';

const tons = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

function transporAcorde(acorde, diff) {
  const raizMatch = acorde.match(/^([A-G]#?b?)/i);
  if (!raizMatch) return acorde;
  
  const raiz = raizMatch[1].toUpperCase().replace('BB', 'B').replace('B', 'Bb');
  const idx = tons.indexOf(raiz);
  if (idx === -1) return acorde;

  const novaRaiz = tons[(idx + diff + 12) % 12];
  return acorde.replace(raiz, novaRaiz);
}

function transporCifra(texto, tomOriginal, tomNovo) {
  if (tomOriginal === tomNovo) return texto;

  const idxOrig = tons.indexOf(tomOriginal);
  const idxNovo = tons.indexOf(tomNovo);
  const diff = idxNovo - idxOrig;

  // Transpõe acordes (suporta C/G, Am7, etc.)
  return texto.replace(/\b([A-G]#?b?)(m|°|aug|dim|sus|add|maj|min)?(\d{0,2})(\/[A-G]#?b?)?\b/gi, (match) => {
    return transporAcorde(match, diff);
  });
}

function App() {
  const [musicas, setMusicas] = useState([]);
  const [busca, setBusca] = useState('');
  const [selecionada, setSelecionada] = useState(null);
  const [tomAtual, setTomAtual] = useState('');

  useEffect(() => {
    const cifrasRef = ref(db, 'cifras');
    onValue(cifrasRef, (snapshot) => {
      const data = snapshot.val();
      if (data) {
        setMusicas(Object.values(data));
      }
    });
  }, []);

  const filtradas = musicas.filter(m =>
    m.titulo?.toLowerCase().includes(busca.toLowerCase()) ||
    m.artista?.toLowerCase().includes(busca.toLowerCase())
  );

  const cifraExibida = selecionada
    ? transporCifra(selecionada.cifra_original || '', selecionada.tom_original, tomAtual || selecionada.tom_original)
    : '';

  return (
    <div className="container my-4">
      <header className="text-center mb-5">
        <h1 className="display-4 fw-bold text-primary">Selah</h1>
        <p className="lead text-muted">Cifre. Ajuste. Louve.</p>
      </header>

      {!selecionada ? (
        <>
          <input
            type="text"
            className="form-control form-control-lg mb-4"
            placeholder="Buscar por título ou artista..."
            value={busca}
            onChange={e => setBusca(e.target.value)}
          />

          <div className="row g-3">
            {filtradas.map(m => (
              <div key={m.titulo + m.artista} className="col-md-6 col-lg-4">
                <div className="card h-100 shadow-sm cursor-pointer" onClick={() => {
                  setSelecionada(m);
                  setTomAtual(m.tom_original);
                }}>
                  <div className="card-body">
                    <h5 className="card-title">{m.titulo}</h5>
                    <p className="card-text text-muted">
                      {m.artista} • Tom: {m.tom_original}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div>
          <button className="btn btn-outline-secondary mb-3" onClick={() => setSelecionada(null)}>
            ← Voltar à lista
          </button>

          <h2>{selecionada.titulo} – {selecionada.artista}</h2>
          <p className="text-muted">Tom original: {selecionada.tom_original}</p>

          <div className="d-flex gap-3 mb-4 align-items-center">
            <label className="fw-bold">Tom:</label>
            <select
              className="form-select w-auto"
              value={tomAtual}
              onChange={e => setTomAtual(e.target.value)}
            >
              {tons.map(t => <option key={t} value={t}>{t}</option>)}
            </select>

            {tomAtual !== selecionada.tom_original && (
              <button
                className="btn btn-sm btn-outline-primary"
                onClick={() => setTomAtual(selecionada.tom_original)}
              >
                Voltar ao original
              </button>
            )}
          </div>

          <pre className="bg-light p-4 rounded border" style={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap', fontSize: '1.1rem' }}>
            {cifraExibida || 'Cifra não disponível'}
          </pre>
        </div>
      )}
    </div>
  );
}

export default App;
