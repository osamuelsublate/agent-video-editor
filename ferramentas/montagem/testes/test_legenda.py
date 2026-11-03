"""A legenda no ASS: a frase com a palavra falada acendendo e a placa escura atrás (legível em tela branca)."""
from montagem import legenda


def eventos(blocos, w=1080, h=1920):
    return [l for l in legenda.ass(blocos, w, h).splitlines() if l.startswith('Dialogue')]


def test_cada_palavra_acende_no_seu_tempo():
    ev = eventos([{'ini': 1.0, 'fim': 3.0, 'texto': 'documentar todas as', 'y': 0.74, 'tempos': [1.17, 1.6, 2.1]}])
    texto = [e for e in ev if ',Legenda,' in e][0]
    assert '}documentar' in texto and '\\1a&H00&' in texto.split('}documentar')[0]  # a 1ª já entra acesa
    assert f'\\t(600,{600 + round(legenda.ACENDE * 1000)},\\1a&H00&' in texto and f'\\1a&H{legenda.APAGADA:02X}&' in texto
    assert '\\t(1100,' in texto


def test_texto_a_mao_ou_contagem_diferente_fica_todo_aceso():
    for b in ({'ini': 0, 'fim': 1, 'texto': 'Claude Code', 'y': 0.5},
              {'ini': 0, 'fim': 1, 'texto': 'Claude Code agora', 'y': 0.5, 'tempos': [0.0, 0.4]}):
        texto = [e for e in eventos([b]) if ',Legenda,' in e][0]
        assert '\\t(' not in texto and texto.endswith(b['texto'])


def test_placa_atras_da_frase_proporcional_ao_texto():
    curta, longa = (eventos([{'ini': 0, 'fim': 1, 'texto': t, 'y': 0.74}]) for t in ('oi', 'construção do app'))
    placa = [e for e in curta if ',Placa,' in e][0]
    assert placa.startswith('Dialogue: 0,') and '\\p1}m ' in placa and placa.endswith('{\\p0}')
    largura = lambda ev: float([e for e in ev if ',Placa,' in e][0].split('\\p1}m ')[1].split()[0])
    assert largura(longa) < largura(curta) < 0  # a placa da frase longa começa mais à esquerda
    assert [e.split(',')[3] for e in curta] == ['Placa', 'Sombra', 'Legenda']
