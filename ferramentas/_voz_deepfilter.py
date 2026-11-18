"""A limpeza da voz com o DeepFilterNet 3 (do 18: backend/app/_voz_deepfilter.py). NÃO é importado: roda num ambiente
Python à parte (o DeepFilterNet 0.5.6 pede o torchaudio antigo, `voz.DEEPFILTER`), chamado por `voz.limpar`.

    python _voz_deepfilter.py <entrada.wav 48 kHz mono> <saida.wav> <limite em dB | 0 = sem limite>
"""
import sys

import torch
from df.enhance import enhance, init_df, load_audio, save_audio

BLOCO = 60  # s por vez: um bruto de 44 min de uma vez estourou a memória da placa (CUDA out of memory, VSL Black26)
SOBRA = 1  # s que dois blocos vizinhos limpam em comum, emendados com uma rampa (sem degrau no ruído de fundo)


def main() -> None:
    entrada, saida, limite = sys.argv[1], sys.argv[2], float(sys.argv[3])
    modelo, estado, _ = init_df(log_level='ERROR', log_file=None)
    audio, _ = load_audio(entrada, sr=estado.sr())
    sr, n = estado.sr(), audio.shape[-1]
    passo, sobra = BLOCO * sr, SOBRA * sr
    limpo = torch.zeros_like(audio)
    ini = 0
    while ini < n:
        fim = min(n, ini + passo + sobra)
        pedaco = enhance(modelo, estado, audio[..., ini:fim], atten_lim_db=limite or None).cpu()
        if ini == 0:
            limpo[..., ini:fim] = pedaco
        else:  # a sobra: o bloco anterior sai em rampa e este entra
            k = min(sobra, fim - ini)
            rampa = torch.linspace(0, 1, k)
            limpo[..., ini:ini + k] = limpo[..., ini:ini + k] * (1 - rampa) + pedaco[..., :k] * rampa
            limpo[..., ini + k:fim] = pedaco[..., k:]
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if fim >= n:
            break
        ini += passo
    save_audio(saida, limpo, sr)


if __name__ == '__main__':
    main()
