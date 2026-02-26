// App.jsx
import { useState, useEffect } from 'react';
import { db } from './firebase.js';
import { ref, onValue } from 'firebase/database';
import './App.css';

const tons = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

function transporAcorde(acorde, diff) {
  const raizMatch = acorde.match(/^([A-G]#?b?)/i);
  if (!raizMatch) return acorde;

  let raiz = raizMatch[1].toUpperCase();
  if (raiz === 'BB') raiz = 'B';
  if (raiz === 'B') raiz = 'Bb';

  const idx = tons.indexOf(raiz);
  if (idx === -1) return acorde;

  const novaRaiz = tons[(idx + diff + 12) % 12];
  return acorde.replace(raizMatch[0], novaRaiz);
}

function transporCifra(texto, tomOriginal, tomNovo) {
  if (!tomOriginal || tomOriginal === tomNovo) return texto;

  const idxOrig = tons.indexOf(tomOriginal);
  const idxNovo = tons.indexOf(tomNovo);
  if (idxOrig === -1 || idxNovo === -1) return texto;

  const diff = idxNovo - idxOrig;

  return texto.replace(
    /\b([A-G]#?b?)(°|º|m|min|maj|aug|dim|sus|add)?(\d{0,2})(\/[A-G]#?b?)?\b/gi,
    (match) => transporAcorde(match, diff)
  );
}

function App() {
  const [musicas, setMusicas] = useState([]);
  const [busca, setBusca] = useState('');
  const [musicaSelecionada, setMusicaSelecionada] = useState(null);
  const [tomSelecionado, setTomSelecionado] = useState('');
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(null);

  useEffect(() => {
    const cifrasRef = ref(db, 'cifras');
    const unsubscribe = onValue(cifrasRef, (snapshot) => {
      setLoading(false);
      const data = snapshot.val();
      if (data) {
        const lista = Object.values(data);
        lista.sort((a, b) => a.titulo.localeCompare(b.titulo, 'pt-BR'));
        setMusicas(lista);
      } else {
        setMusicas([]);
      }
    }, (error) => {
      setLoading(false);
      setErro('Erro ao carregar dados: ' + error.message);
    });

    return () => unsubscribe();
  }, []);

  const musicasFiltradas = musicas.filter((m) =>
    (m.titulo || '').toLowerCase().includes(busca.toLowerCase()) ||
    (m.artista || '').toLowerCase().includes(busca.toLowerCase())
  );

  const cifraParaExibir = musicaSelecionada
    ? transporCifra(
        musicaSelecionada.cifra_original || '',
        musicaSelecionada.tom_original,
        tomSelecionado || musicaSelecionada.tom_original
      )
    : '';

  const voltarAoOriginal = () => {
    if (musicaSelecionada?.tom_original) {
      setTomSelecionado(musicaSelecionada.tom_original);
    }
  };

  if (loading) {
    return <div className="container text-center py-5"><p>Carregando músicas...</p></div>;
  }

  if (erro) {
    return <div className="container text-center py-5"><p>{erro}</p></div>;
  }

  return (
    <div className="container py-4">
      {/* Cabeçalho */}
      <header className="text-center mb-5">
        <h1 className="display-4 fw-bold text-primary">Selah</h1>
        <p className="lead text-muted fst-italic">
          Cifre. Ajuste. Louve.
        </p>
      </header>

      {!musicaSelecionada ? (
        <>
          <div className="mb-4">
            <input
              type="text"
              className="form-control form-control-lg"
              placeholder="Buscar por título ou artista..."
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
          </div>

          {musicasFiltradas.length === 0 ? (
            <div className="text-center py-5 text-muted">
              <h4>Nenhuma música encontrada</h4>
              <p>Tente outra busca ou verifique se o processamento já ocorreu.</p>
            </div>
          ) : (
            <div className="row g-3">
              {musicasFiltradas.map((musica) => (
                <div key={musica.titulo + musica.artista} className="col-md-6 col-lg-4">
                  <div
                    className="card h-100 shadow-sm border-0 musica-card"
                    onClick={() => {
                      setMusicaSelecionada(musica);
                      setTomSelecionado(musica.tom_original || 'C');
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    <div className="card-body">
                      <h5 className="card-title fw-bold">{musica.titulo}</h5>
                      <p className="card-text text-muted">
                        {musica.artista || 'Artista não informado'}
                        <br />
                        <small>Tom original: {musica.tom_original || '?'}</small>
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <div>
          <button
            className="btn btn-outline-secondary mb-4"
            onClick={() => setMusicaSelecionada(null)}
          >
            ← Voltar para a lista
          </button>

          <h2 className="mb-2">{musicaSelecionada.titulo}</h2>
          <h5 className="text-muted mb-4">
            {musicaSelecionada.artista || '—'}
          </h5>

          <div className="d-flex flex-wrap gap-3 align-items-center mb-4">
            <label className="fw-bold me-2">Tom atual:</label>
            <select
              className="form-select w-auto"
              value={tomSelecionado}
              onChange={(e) => setTomSelecionado(e.target.value)}
            >
              {tons.map((tom) => (
                <option key={tom} value={tom}>
                  {tom}
                </option>
              ))}
            </select>

            {tomSelecionado !== musicaSelecionada.tom_original && (
              <button className="btn btn-outline-primary btn-sm" onClick={voltarAoOriginal}>
                Voltar ao original ({musicaSelecionada.tom_original})
              </button>
            )}
          </div>

          <pre className="cifra bg-light p-4 rounded border shadow-sm">
            {cifraParaExibir || '[Cifra não disponível ou vazia]'}
          </pre>
        </div>
      )}
    </div>
  );
}

export default App;