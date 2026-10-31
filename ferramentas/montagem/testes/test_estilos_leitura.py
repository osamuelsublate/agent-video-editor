"""Os estilos (a cópia inicial, a biblioteca nova e o --estilo do brief de motion) e a regra da checagem de leitura."""
import re

import pytest

import base
import inserts
import leitura

INICIAL = base.INICIAL / 'estilos'
ETAPA = base.RAIZ / '.claude' / 'skills' / 'editor' / 'etapas' / '06-motions-e-elementos.md'


def test_a_copia_tem_os_66_guias_sem_comandos():
    guias = sorted(INICIAL.glob('*/STYLE.md'))
    assert len(guias) == 66
    assert all((g.parent / 'DEMO.md').is_file() for g in guias)
    assert not (INICIAL / '_template').exists()
    for f in ('LICENSE', 'ORIGEM.md', 'COMO-USAR.md', 'README.md'):
        assert (INICIAL / f).is_file()
    proibido = re.compile(r'setup\.sh|build\.sh|fetch\.sh|footage\.py|pip install|https?://|api[_ -]key', re.I)
    assert not [g for g in [*guias, *INICIAL.glob('*/DEMO.md')] if proibido.search(g.read_text(encoding='utf-8'))]


def test_os_slugs_da_etapa_existem():
    tabela = ETAPA.read_text(encoding='utf-8').split('**Estilo**')[1].split('**Pedido')[0]
    slugs = re.findall(r'`([a-z0-9-]+)`', tabela.split('|---|---|')[1])
    assert len(slugs) >= 10
    assert not [s for s in slugs if not (INICIAL / s / 'STYLE.md').is_file()]


def test_biblioteca_nova_recebe_os_estilos_e_a_que_tem_fica_como_esta(tmp_path, monkeypatch):
    monkeypatch.setattr(base, 'BIBLIOTECA', tmp_path / 'biblioteca')
    monkeypatch.setattr(base, 'PROJETOS', tmp_path / 'projetos')
    base.preparar_biblioteca()
    assert (tmp_path / 'biblioteca/estilos/news-package/STYLE.md').is_file()
    assert (tmp_path / 'biblioteca/estilos/COMO-USAR.md').is_file()
    guia = tmp_path / 'biblioteca/estilos/news-package/STYLE.md'
    guia.write_text('editado')
    base.preparar_biblioteca()
    assert guia.read_text() == 'editado'


@pytest.fixture
def com_estilos(tmp_path, monkeypatch):
    (tmp_path / 'estilos/news-package').mkdir(parents=True)
    (tmp_path / 'estilos/news-package/STYLE.md').write_text('x')
    monkeypatch.setattr(inserts, 'BIBLIOTECA', tmp_path)
    return tmp_path


def test_linha_do_estilo(com_estilos):
    linha = inserts.linha_estilo('news-package')
    assert str(com_estilos / 'estilos/COMO-USAR.md') in linha and str(com_estilos / 'estilos/news-package/STYLE.md') in linha


@pytest.mark.parametrize('errado', ['news-pakage', '../news-package', 'NEWS'])
def test_estilo_errado_erra_com_mensagem(com_estilos, errado):
    with pytest.raises(SystemExit, match='Estilo não encontrado'):
        inserts.linha_estilo(errado)
    with pytest.raises(SystemExit, match='Parecidos: news-package'):
        inserts.linha_estilo('news-pakage')


def test_o_modelo_do_brief_formata_com_e_sem_estilo():
    modelo = (inserts.ETAPAS / '06-brief-motion.md').read_text(encoding='utf-8')
    campos = dict(raiz='/r', preset='novo', projeto='p', pedido='a', formato='vertical', categoria='c', exemplos='/e', palco='1080', duracao='2,5', fala='f')
    texto = modelo.format(extra='Estilo pedido: x', **campos)
    assert 'Estilo pedido: x' in texto and '/r/biblioteca/estilos/COMO-USAR.md' in texto
    assert 'leitura.py novo --formato\nvertical --duracao 2,5' in texto


def quadros(*textos, dur=4.0, passo=0.05):
    """textos: (texto, ini, fim, {el, pai, tam, dentro}); uma lista por instante."""
    out = []
    for k in range(int(round(dur / passo)) + 1):
        t = k * passo
        vis = [{'el': o.get('el', i), 'pai': o.get('pai', 100 + i), 'texto': tx, 'tam': o.get('tam', 60), 'dentro': o.get('dentro', True)}
               for i, (tx, a, b, o) in enumerate(textos) if a <= t < b]
        out.append({'t': t, 'textos': vis})
    return out


def nota(*textos, dur=4.0):
    return leitura.avaliar(quadros(*textos, dur=dur), 0.05, dur)


def test_regra_do_tempo():
    assert leitura.precisa('abc') == pytest.approx(1.7)
    assert nota(('Uma frase de vinte e oito letras', 0, 4, {}))[0]['ok']
    n = nota(('Uma frase de vinte e oito letras', 0, 1, {}))[0]
    assert not n['ok'] and 'curto' in n['motivo']


def test_fora_do_palco():
    assert 'nunca inteiro' in nota(('Texto cortado', 0, 4, {'dentro': False}))[0]['motivo']


def test_entrada_cortada_rapida_passa():
    q = quadros(('Texto que entra', 0, 0.3, {'dentro': False, 'el': 1}), ('Texto que entra', 0.3, 4, {'el': 1}))
    assert leitura.avaliar(q, 0.05, 4.0)[0]['ok']


def test_digitacao_conta_do_primeiro_quadro_e_o_tamanho_final():
    frase = 'Digitando esta frase comprida aqui'
    q = [{'t': k * 0.05, 'textos': [{'el': 1, 'pai': 2, 'texto': frase[:k + 1], 'tam': 60, 'dentro': True}]} for k in range(60)]
    n = leitura.avaliar(q, 0.05, 3.0)
    assert len(n) == 1 and n[0]['tipo'] == 'cresce' and n[0]['texto'].startswith('Digitando esta frase')
    assert n[0]['ini'] == 0 and not n[0]['ok']  # 3 s < 29 ÷ 15 + 1,5


def test_contador_e_spinner_sao_um_texto_so():
    q = [{'t': k * 0.05, 'textos': [{'el': 1, 'pai': 2, 'texto': f'{k * 10} tokens', 'tam': 60, 'dentro': True}]} for k in range(60)]
    assert len(leitura.avaliar(q, 0.05, 3.0)) == 1
    q = [{'t': k * 0.05, 'textos': [{'el': 1, 'pai': 2, 'texto': '✢✳✶'[k % 3] + ' Lendo arquivos', 'tam': 60, 'dentro': True}]} for k in range(60)]
    assert len(leitura.avaliar(q, 0.05, 3.0)) == 1


def test_palavra_por_palavra_acumulando_e_trocando():
    # como no lettering: cada palavra entra e fica, no mesmo pai; o 1,2 s não dá a folga de 1,5 s, mas passa
    n = nota(('Image', 0.05, 1.2, {'pai': 9}), ('to', 0.27, 1.2, {'pai': 9}), ('Code', 0.49, 1.2, {'pai': 9}), dur=1.2)
    assert len(n) == 1 and n[0]['tipo'] == 'palavra a palavra' and n[0]['ok']
    # uma trocando a outra no mesmo elemento
    n = nota(('Uma', 0, 0.4, {'el': 1, 'pai': 9}), ('palavra', 0.4, 0.8, {'el': 1, 'pai': 9}), ('cada', 0.8, 1.2, {'el': 1, 'pai': 9}), dur=1.2)
    assert len(n) == 1 and n[0]['ok']
    # rápida demais reprova
    n = nota(('Uma', 0, 0.1, {'pai': 9}), ('voando', 0.1, 0.2, {'pai': 9}), ('agora', 0.2, 0.3, {'pai': 9}))
    assert 'rápida' in n[0]['motivo']


def test_bloco_que_cresce_em_palavras_inteiras():
    estados = ['Uma', 'Uma frase', 'Uma frase toda']
    q = [{'t': k * 0.05, 'textos': [{'el': 1, 'pai': 2, 'texto': estados[min(k // 8, 2)], 'tam': 60, 'dentro': True}]} for k in range(25)]
    n = leitura.avaliar(q, 0.05, 1.2)
    assert n[0]['tipo'] == 'palavra a palavra' and n[0]['ok']


def test_palavras_soltas_juntas_nao_sao_a_excecao():
    n = nota(('Haiku', 0.2, 1.2, {'pai': 9}), ('Sonnet', 0.2, 1.2, {'pai': 9}), dur=1.2)
    assert len(n) == 2 and not any(x['ok'] for x in n)


def test_o_digitado_que_vira_balao_e_o_mesmo_texto():
    n = nota(('Instala essa skill', 0, 1.5, {'el': 1}), ('Instala essa skill', 1.8, 4, {'el': 2}))
    assert len(n) == 1 and n[0]['ok']


def test_fora_da_regra_miudo_textura_e_cursor():
    assert nota(('perf-audit — claude — 72×20', 0, 0.5, {'tam': 34}))[0]['tipo'].startswith('miúdo')
    assert nota(('▍', 0, 0.2, {}), ('12', 0, 0.2, {})) == []
    parede = [(f'Curso número {letra}', 0.1 * k, 0.4 + 0.1 * k, {}) for k, letra in enumerate('abcdefghijklmnopqrstuvwxyz'[:20])]
    n = nota(*parede)
    assert len(n) == 1 and n[0]['ok'] and n[0]['tipo'].startswith('textura')
