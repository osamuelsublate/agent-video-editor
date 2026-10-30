// do 18: frontend/src/inserts/ComentarioIG.tsx (só a marcação do card, sem o arraste nem o painel)
import { noQuadro } from './divisao'
import type { V } from './desenho'

/** O card de comentário do Instagram (plano Comentário + insert + ator; SPEC §8.3): foto, usuário e tempo borrados,
 *  o texto, "Responder" e "Ver tradução". Na Inter, com os tamanhos que dão as maiúsculas da SF do iPhone. */
export type Comentario = { texto: string | null; avatar: number; usuario: string; tempo: string; traducao: boolean; x: number; y: number; escala: number }
const COMENTARIO_PADRAO: Comentario = { texto: null, avatar: 0, usuario: 'usuario.do.ig', tempo: '4 sem', traducao: true, x: 50, y: 50, escala: 1 }
/** O comentário do insert; sem posição salva (nunca arrastado), fica no lugar automático da divisão (`auto`). */
export const comentarioDe = (x: { comentario?: Partial<Comentario> }, auto?: { x: number; y: number }): Comentario => ({
  ...COMENTARIO_PADRAO,
  ...(auto ?? {}),
  ...(x.comentario ?? {}),
})

const FONTE_IG = 'Inter, sans-serif'

/** O card (centro em `x`, `y` %; largura 75% × escala), sempre inteiro no quadro (`divisao.noQuadro`). */
export function cardComentario(c: Comentario, texto: string): V {
  const pos = noQuadro(c, texto)
  const u = (v: number) => `${v * c.escala}cqw` // medidas proporcionais à largura do vídeo
  return {
    chave: 'comentario',
    classe: 'pointer-events-none absolute inset-0 z-10',
    estilo: { containerType: 'size' },
    filhos: [
      {
        chave: 'card',
        classe: 'absolute flex centrado items-start bg-white text-black sombra-comentario select-none',
        estilo: { left: `${pos.x}%`, top: `${pos.y}%`, fontFamily: FONTE_IG, gap: u(2.6), padding: `${u(2.6)} ${u(3.2)}`, borderRadius: u(3), width: `${Math.min(75 * c.escala, 96)}%` },
        filhos: [
          // 5 fotos de perfil de pessoas que não existem (rostos gerados por IA), em render/avatares/
          {
            chave: 'avatar',
            tag: 'img',
            classe: 'rounded-full object-cover shrink-0',
            atributos: { src: `/render/avatares/${(c.avatar % 5) + 1}.jpg`, alt: '', draggable: 'false' },
            estilo: { filter: 'blur(2.5px)', width: u(8.2), height: u(8.2) },
          },
          {
            chave: 'corpo',
            classe: 'min-w-0 flex-1',
            estilo: { lineHeight: 1.3 },
            filhos: [
              {
                chave: 'usuario',
                classe: 'flex items-baseline',
                estilo: { gap: u(1.6), fontSize: u(2.81), filter: `blur(${u(0.55)})` },
                filhos: [
                  { chave: 'nome', tag: 'span', classe: 'font-semibold cor-262626', texto: c.usuario },
                  { chave: 'tempo', tag: 'span', classe: 'cor-737373', texto: c.tempo },
                ],
              },
              { chave: 'texto', tag: 'p', classe: 'cor-000 quebra-qualquer', estilo: { fontSize: u(3.49), marginTop: u(0.4) }, texto },
              {
                chave: 'acoes',
                classe: 'flex font-semibold cor-737373',
                estilo: { gap: u(4), fontSize: u(2.81), marginTop: u(1.2) },
                filhos: [{ chave: 'responder', tag: 'span', texto: 'Responder' }, c.traducao && { chave: 'traducao', tag: 'span', texto: 'Ver tradução' }],
              },
            ],
          },
        ],
      },
    ],
  }
}
