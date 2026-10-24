"""Apresentações holográficas: o assunto vira um objeto 3D em peças + o roteiro que o Jarvis fala, peça por peça.

A tela (web/holograma.js, three.js) desenha as peças com cara de holograma; cada frase falada acende a(s) peça(s)
daquele trecho e, quando o roteiro pede, o objeto "explode" (as peças se separam pra mostrar por dentro).
Dois modelos feitos à mão (camadas da Terra e peças do computador); o resto o cérebro monta com formas simples.
"""
import json
import math
import re
import unicodedata

import cerebro


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


PI = math.pi
# virar o corte da esfera (o quarto que falta) pra frente da câmera
CORTE_PRA_FRENTE = [0, 3 * PI / 4, 0]

TERRA = {
    "titulo": "As camadas da Terra",
    "zoom": 10.5,
    "intro": "A Terra tem quatro camadas principais: crosta, manto, núcleo externo e núcleo interno. Vou abrir ela pra você ver.",
    "partes": [
        {"nome": "Crosta", "forma": "esfera_cortada", "tam": [2.0], "cor": "#4fe3ff", "pos": [0, 0, 0], "rot": CORTE_PRA_FRENTE,
         "explode": [0, 1.5, 0], "ancora": [0, 0.88, 1.74]},
        {"nome": "Manto", "forma": "esfera_cortada", "tam": [1.9], "cor": "#ff7a2f", "pos": [0, 0, 0], "rot": CORTE_PRA_FRENTE,
         "explode": [0, 0.5, 0], "ancora": [0, 0.68, 1.34]},
        {"nome": "Núcleo externo", "forma": "esfera_cortada", "tam": [1.1], "cor": "#ffc23d", "pos": [0, 0, 0], "rot": CORTE_PRA_FRENTE,
         "explode": [0, -0.45, 0], "ancora": [0, 0.35, 0.72]},
        {"nome": "Núcleo interno", "forma": "esfera", "tam": [0.45], "cor": "#fff6b0", "pos": [0, 0, 0],
         "explode": [0, -1.2, 0], "ancora": [0, 0.1, 0.25]},
    ],
    "passos": [
        {"fala": "Por fora, a crosta: a casca fininha onde a gente vive. Tem de 5 a 70 quilômetros de espessura, menos de um por cento do planeta.",
         "destaque": ["Crosta"]},
        {"fala": "Embaixo dela, o manto: rocha quente e pastosa, quase 2.900 quilômetros de espessura. É o movimento dele que arrasta as placas tectônicas.",
         "destaque": ["Manto"]},
        {"fala": "Depois vem o núcleo externo, de ferro e níquel líquidos. Esse metal girando é o que cria o campo magnético da Terra.",
         "destaque": ["Núcleo externo"], "explodir": True},
        {"fala": "E bem no centro, o núcleo interno: uma bola sólida de ferro a uns 5.400 graus, quente como a superfície do Sol, sólida por causa da pressão.",
         "destaque": ["Núcleo interno"], "explodir": True},
        {"fala": "Juntando tudo: crosta, manto, núcleo externo e núcleo interno. Pode girar o modelo com o mouse.",
         "destaque": ["Crosta", "Manto", "Núcleo externo", "Núcleo interno"]},
    ],
}

COMPUTADOR = {
    "titulo": "As peças de um computador",
    "intro": "Vou desmontar um computador pra você: são sete peças principais dentro do gabinete.",
    "partes": [
        {"nome": "Gabinete", "forma": "caixa", "tam": [3.2, 3.6, 1.7], "cor": "#4fe3ff", "pos": [0, 0, 0], "explode": [0, 0, -0.4], "fantasma": True},
        {"nome": "Placa-mãe", "forma": "placa", "tam": [2.4, 2.9, 0.06], "cor": "#2ee88a", "pos": [0.1, 0.15, -0.72], "explode": [0, 0, -1.0]},
        {"nome": "Processador", "forma": "caixa", "tam": [0.45, 0.45, 0.08], "cor": "#ffd23d", "pos": [-0.25, 0.75, -0.62], "explode": [0, 0.5, 1.0]},
        {"nome": "Cooler", "forma": "cilindro", "tam": [0.36, 0.3], "cor": "#9ad8ff", "pos": [-0.25, 0.75, -0.38], "rot": [PI / 2, 0, 0], "explode": [0, 0.9, 1.9]},
        {"nome": "Memória RAM", "forma": "caixa", "tam": [0.28, 1.05, 0.26], "cor": "#c77dff", "pos": [0.45, 0.75, -0.55], "explode": [1.1, 0.8, 1.0]},
        {"nome": "Placa de vídeo", "forma": "caixa", "tam": [2.0, 0.26, 0.75], "cor": "#ff5d8f", "pos": [-0.1, -0.45, -0.3], "explode": [0, -0.3, 1.6]},
        {"nome": "SSD", "forma": "placa", "tam": [0.7, 0.22, 0.05], "cor": "#7cff6b", "pos": [0.65, -0.05, -0.66], "explode": [1.4, -0.2, 0.9]},
        {"nome": "Fonte", "forma": "caixa", "tam": [1.4, 0.8, 1.2], "cor": "#ff9b3d", "pos": [-0.75, -1.35, 0.05], "explode": [-1.0, -0.9, 0.9]},
    ],
    "passos": [
        {"fala": "A placa-mãe é a base de tudo: é nela que todas as outras peças se encaixam e conversam.", "destaque": ["Placa-mãe"], "explodir": True},
        {"fala": "O processador é o cérebro: faz as contas. Em cima dele vai o cooler, que tira o calor pra ele não fritar.",
         "destaque": ["Processador", "Cooler"], "explodir": True},
        {"fala": "A memória RAM guarda o que está aberto agora. É rápida, mas esquece tudo quando desliga.", "destaque": ["Memória RAM"], "explodir": True},
        {"fala": "O SSD é onde ficam seus arquivos e o Windows, guardados mesmo desligado.", "destaque": ["SSD"], "explodir": True},
        {"fala": "A placa de vídeo desenha a imagem na tela; pra jogo e 3D é ela que faz o trabalho pesado.", "destaque": ["Placa de vídeo"], "explodir": True},
        {"fala": "E a fonte transforma a energia da tomada na que as peças usam. Fechando o gabinete, tá montado.",
         "destaque": ["Fonte", "Gabinete"]},
    ],
}

# órgãos "de verdade" (solido=True: o holograma.js preenche opaco, não o wireframe fantasma)
CORACAO = {
    "titulo": "O coração humano",
    "zoom": 9,
    "intro": "O coração tem quatro câmaras e os grandes vasos. Vou abrir ele pra você ver por dentro.",
    "partes": [
        {"nome": "Átrio direito", "forma": "esfera", "tam": [0.55], "cor": "#c94e58", "pos": [0.6, 0.7, 0.1], "solido": True, "explode": [1.3, 1.0, 0.4]},
        {"nome": "Átrio esquerdo", "forma": "esfera", "tam": [0.5], "cor": "#b83b47", "pos": [-0.5, 0.75, -0.2], "solido": True, "explode": [-1.2, 1.1, -0.6]},
        {"nome": "Ventrículo direito", "forma": "esfera", "tam": [0.8], "cor": "#e06b74", "pos": [0.5, -0.35, 0.2], "solido": True, "explode": [1.4, -0.7, 0.5]},
        {"nome": "Ventrículo esquerdo", "forma": "esfera", "tam": [0.95], "cor": "#d64550", "pos": [-0.3, -0.45, 0], "solido": True, "explode": [-1.4, -0.9, 0]},
        {"nome": "Aorta", "forma": "cilindro", "tam": [0.22, 1.6], "cor": "#f0a0a8", "pos": [-0.05, 1.2, 0], "rot": [0.3, 0, 0.2], "solido": True, "explode": [0, 1.7, 0]},
        {"nome": "Artéria pulmonar", "forma": "cilindro", "tam": [0.2, 1.3], "cor": "#8fb8ff", "pos": [0.35, 1.05, 0.3], "rot": [0.2, 0, -0.2], "solido": True, "explode": [0.7, 1.5, 0.6]},
    ],
    "passos": [
        {"fala": "O sangue chega pelo átrio direito, a câmara de cima da direita, trazendo o sangue já usado pelo corpo.", "destaque": ["Átrio direito"]},
        {"fala": "Dele o sangue desce pro ventrículo direito, que bombeia pro pulmão pegar oxigênio.", "destaque": ["Ventrículo direito", "Artéria pulmonar"], "explodir": True},
        {"fala": "Voltando do pulmão cheio de oxigênio, o sangue entra no átrio esquerdo.", "destaque": ["Átrio esquerdo"], "explodir": True},
        {"fala": "E o ventrículo esquerdo, o mais forte de todos, empurra esse sangue pro corpo inteiro pela aorta.", "destaque": ["Ventrículo esquerdo", "Aorta"], "explodir": True},
        {"fala": "Juntando: dois átrios em cima, dois ventrículos embaixo, e os grandes vasos. Bate umas cem mil vezes por dia. Pode girar com o mouse.",
         "destaque": ["Átrio direito", "Átrio esquerdo", "Ventrículo direito", "Ventrículo esquerdo", "Aorta", "Artéria pulmonar"]},
    ],
}

CEREBRO = {
    "titulo": "O cérebro humano",
    "zoom": 9.5,
    "intro": "O cérebro tem lobos, cada um com sua função, mais o cerebelo e o tronco. Vou separar pra você ver.",
    "partes": [
        {"nome": "Lobo frontal", "forma": "esfera", "tam": [0.7], "cor": "#ff9bb0", "pos": [0, 0.25, 0.8], "solido": True, "explode": [0, 0.6, 1.5]},
        {"nome": "Lobo parietal", "forma": "esfera", "tam": [0.62], "cor": "#ffb38f", "pos": [0, 0.7, -0.1], "solido": True, "explode": [0, 1.5, 0]},
        {"nome": "Lobo occipital", "forma": "esfera", "tam": [0.52], "cor": "#c9a0ff", "pos": [0, 0.2, -0.85], "solido": True, "explode": [0, 0.4, -1.5]},
        {"nome": "Lobos temporais", "forma": "esfera", "tam": [0.5], "cor": "#9ad8ff", "pos": [0.75, -0.2, 0.2], "solido": True, "explode": [1.5, -0.2, 0.3]},
        {"nome": "Cerebelo", "forma": "esfera", "tam": [0.48], "cor": "#8fd6a0", "pos": [0, -0.55, -0.7], "solido": True, "explode": [0, -1.2, -1.1]},
        {"nome": "Tronco encefálico", "forma": "cilindro", "tam": [0.17, 0.9], "cor": "#d6d0c8", "pos": [0, -0.95, -0.35], "rot": [0.3, 0, 0], "solido": True, "explode": [0, -1.7, -0.5]},
    ],
    "passos": [
        {"fala": "Na frente, o lobo frontal: é onde você decide, planeja e controla os movimentos. É o chefe da casa.", "destaque": ["Lobo frontal"]},
        {"fala": "Em cima, o lobo parietal, que junta o tato, a temperatura e a noção de onde seu corpo está no espaço.", "destaque": ["Lobo parietal"], "explodir": True},
        {"fala": "Dos lados, os lobos temporais: audição, linguagem e boa parte da memória.", "destaque": ["Lobos temporais"], "explodir": True},
        {"fala": "Atrás, o lobo occipital, que cuida só de uma coisa: enxergar. Toda a visão é processada aqui.", "destaque": ["Lobo occipital"], "explodir": True},
        {"fala": "Embaixo, o cerebelo garante equilíbrio e coordenação, e o tronco encefálico controla o que não para nunca: respiração e batimento.", "destaque": ["Cerebelo", "Tronco encefálico"], "explodir": True},
        {"fala": "Junto, é isso: os lobos por fora, o cerebelo e o tronco por baixo. Uns oitenta e seis bilhões de neurônios aí dentro.",
         "destaque": ["Lobo frontal", "Lobo parietal", "Lobo occipital", "Lobos temporais", "Cerebelo", "Tronco encefálico"]},
    ],
}

CORPO = {
    "titulo": "O corpo humano",
    "zoom": 15,
    "intro": "Vou te mostrar o corpo e, por dentro dele, os órgãos principais. Posso separar cada um.",
    "partes": [
        {"nome": "Cabeça", "forma": "esfera", "tam": [0.45], "cor": "#4fe3ff", "pos": [0, 2.5, 0], "fantasma": True, "sem_rotulo": True, "explode": [0, 0.3, 0]},
        {"nome": "Tronco", "forma": "caixa", "tam": [1.5, 2.2, 0.8], "cor": "#4fe3ff", "pos": [0, 0.7, 0], "fantasma": True, "sem_rotulo": True, "explode": [0, 0, 0]},
        {"nome": "Braço esquerdo", "forma": "cilindro", "tam": [0.17, 2.0], "cor": "#4fe3ff", "pos": [-1.0, 0.8, 0], "rot": [0, 0, 0.2], "fantasma": True, "sem_rotulo": True, "explode": [-0.6, 0, 0]},
        {"nome": "Braço direito", "forma": "cilindro", "tam": [0.17, 2.0], "cor": "#4fe3ff", "pos": [1.0, 0.8, 0], "rot": [0, 0, -0.2], "fantasma": True, "sem_rotulo": True, "explode": [0.6, 0, 0]},
        {"nome": "Perna esquerda", "forma": "cilindro", "tam": [0.22, 2.3], "cor": "#4fe3ff", "pos": [-0.4, -1.7, 0], "fantasma": True, "sem_rotulo": True, "explode": [-0.3, -0.4, 0]},
        {"nome": "Perna direita", "forma": "cilindro", "tam": [0.22, 2.3], "cor": "#4fe3ff", "pos": [0.4, -1.7, 0], "fantasma": True, "sem_rotulo": True, "explode": [0.3, -0.4, 0]},
        {"nome": "Cérebro", "forma": "esfera", "tam": [0.3], "cor": "#ff9bb0", "pos": [0, 2.5, 0.05], "solido": True, "explode": [1.6, 0.8, 0.6]},
        {"nome": "Pulmão esquerdo", "forma": "esfera", "tam": [0.42], "cor": "#e59aa5", "pos": [-0.5, 1.2, 0.1], "solido": True, "explode": [-1.8, 0.8, 0.6]},
        {"nome": "Pulmão direito", "forma": "esfera", "tam": [0.42], "cor": "#e59aa5", "pos": [0.5, 1.2, 0.1], "solido": True, "explode": [1.8, 0.8, 0.6]},
        {"nome": "Coração", "forma": "esfera", "tam": [0.33], "cor": "#d64550", "pos": [-0.12, 1.05, 0.28], "solido": True, "explode": [-1.6, 0.4, 1.1]},
        {"nome": "Fígado", "forma": "esfera", "tam": [0.42], "cor": "#9a6a44", "pos": [0.3, 0.25, 0.25], "solido": True, "explode": [1.7, -0.3, 1.0]},
        {"nome": "Estômago", "forma": "esfera", "tam": [0.33], "cor": "#e0b080", "pos": [-0.35, 0.3, 0.3], "solido": True, "explode": [-1.7, -0.2, 1.1]},
        {"nome": "Intestinos", "forma": "esfera", "tam": [0.5], "cor": "#d99a6c", "pos": [0, -0.4, 0.25], "solido": True, "explode": [0, -1.6, 1.2]},
    ],
    "passos": [
        {"fala": "Esse é o corpo todo. Vou abrir e mostrar os órgãos principais, um por um.", "destaque": []},
        {"fala": "No alto, protegido pelo crânio, o cérebro: comanda tudo, do pensamento ao movimento.", "destaque": ["Cérebro"], "explodir": True},
        {"fala": "No peito, os dois pulmões puxam o ar, e entre eles o coração bombeia o sangue pro corpo inteiro.", "destaque": ["Pulmão esquerdo", "Pulmão direito", "Coração"], "explodir": True},
        {"fala": "Logo abaixo, o fígado filtra e processa quase tudo que você come e bebe.", "destaque": ["Fígado"], "explodir": True},
        {"fala": "Do outro lado, o estômago quebra a comida, e embaixo os intestinos terminam a digestão e absorvem os nutrientes.", "destaque": ["Estômago", "Intestinos"], "explodir": True},
        {"fala": "Juntando tudo de volta no corpo: cérebro, pulmões, coração, fígado, estômago e intestinos. Pode girar pra ver de todos os lados.",
         "destaque": ["Cérebro", "Pulmão esquerdo", "Pulmão direito", "Coração", "Fígado", "Estômago", "Intestinos"]},
    ],
}

ESQUELETO = {
    "titulo": "O esqueleto humano",
    "zoom": 15,
    "intro": "O esqueleto são 206 ossos que sustentam e protegem o corpo. Vou mostrar as partes principais.",
    "partes": [
        {"nome": "Crânio", "forma": "esfera", "tam": [0.5], "cor": "#ece3d0", "pos": [0, 2.6, 0], "solido": True, "explode": [0, 0.9, 0]},
        {"nome": "Coluna vertebral", "forma": "cilindro", "tam": [0.13, 2.6], "cor": "#ded2b8", "pos": [0, 0.9, -0.12], "solido": True, "explode": [0, 0, -1.2]},
        {"nome": "Caixa torácica", "forma": "toro", "tam": [0.85, 0.12], "cor": "#e6dcc2", "pos": [0, 1.45, 0], "rot": [1.5708, 0, 0], "solido": True, "explode": [0, 1.2, 0.9]},
        {"nome": "Pélvis", "forma": "toro", "tam": [0.5, 0.15], "cor": "#ded2b8", "pos": [0, -0.25, 0], "rot": [1.5708, 0, 0], "solido": True, "explode": [0, -0.8, 0.9]},
        {"nome": "Braço esquerdo", "forma": "cilindro", "tam": [0.1, 1.9], "cor": "#ece3d0", "pos": [-0.95, 0.9, 0], "rot": [0, 0, 0.2], "solido": True, "explode": [-1.5, 0, 0]},
        {"nome": "Braço direito", "forma": "cilindro", "tam": [0.1, 1.9], "cor": "#ece3d0", "pos": [0.95, 0.9, 0], "rot": [0, 0, -0.2], "solido": True, "explode": [1.5, 0, 0]},
        {"nome": "Perna esquerda", "forma": "cilindro", "tam": [0.14, 2.3], "cor": "#ded2b8", "pos": [-0.35, -1.7, 0], "solido": True, "explode": [-0.7, -0.5, 0]},
        {"nome": "Perna direita", "forma": "cilindro", "tam": [0.14, 2.3], "cor": "#ded2b8", "pos": [0.35, -1.7, 0], "solido": True, "explode": [0.7, -0.5, 0]},
    ],
    "passos": [
        {"fala": "No alto, o crânio: uma caixa de osso que protege o cérebro.", "destaque": ["Crânio"], "explodir": True},
        {"fala": "A coluna vertebral sustenta o corpo em pé e protege a medula espinhal, por dentro dela.", "destaque": ["Coluna vertebral"], "explodir": True},
        {"fala": "A caixa torácica, feita das costelas, protege o coração e os pulmões.", "destaque": ["Caixa torácica"], "explodir": True},
        {"fala": "A pélvis liga o tronco às pernas e segura o peso do corpo quando você senta ou anda.", "destaque": ["Pélvis"], "explodir": True},
        {"fala": "E os ossos dos braços e das pernas, os mais longos do corpo, que dão a alavanca pra você se mexer.", "destaque": ["Braço esquerdo", "Braço direito", "Perna esquerda", "Perna direita"], "explodir": True},
        {"fala": "Junto, é a estrutura inteira: 206 ossos que seguram você de pé. Pode girar pra ver por trás.",
         "destaque": ["Crânio", "Coluna vertebral", "Caixa torácica", "Pélvis", "Braço esquerdo", "Braço direito", "Perna esquerda", "Perna direita"]},
    ],
}

MUSCULOS = {
    "titulo": "Os músculos do corpo",
    "zoom": 15,
    "intro": "São mais de 600 músculos. Vou mostrar os grandes grupos que movem o corpo.",
    "partes": [
        {"nome": "Trapézio", "forma": "caixa", "tam": [0.9, 0.45, 0.4], "cor": "#b5473f", "pos": [0, 2.0, -0.1], "solido": True, "explode": [0, 0.8, -0.7]},
        {"nome": "Peitoral", "forma": "caixa", "tam": [1.1, 0.6, 0.4], "cor": "#c25046", "pos": [0, 1.4, 0.3], "solido": True, "explode": [0, 0.5, 1.3]},
        {"nome": "Bíceps", "forma": "esfera", "tam": [0.26], "cor": "#b5473f", "pos": [-0.95, 1.0, 0.1], "solido": True, "explode": [-1.5, 0.3, 0.5]},
        {"nome": "Abdômen", "forma": "caixa", "tam": [0.8, 0.95, 0.35], "cor": "#c25046", "pos": [0, 0.5, 0.35], "solido": True, "explode": [0, -0.4, 1.4]},
        {"nome": "Dorsais", "forma": "caixa", "tam": [1.1, 1.3, 0.35], "cor": "#9c3d36", "pos": [0, 1.0, -0.35], "solido": True, "explode": [0, 0.3, -1.4]},
        {"nome": "Quadríceps", "forma": "caixa", "tam": [0.38, 1.3, 0.42], "cor": "#b5473f", "pos": [-0.35, -1.3, 0.15], "solido": True, "explode": [-1.0, -0.6, 0.9]},
    ],
    "passos": [
        {"fala": "No peito, o peitoral: empurra e abraça, usado todo dia pra levantar e carregar.", "destaque": ["Peitoral"], "explodir": True},
        {"fala": "No braço, o bíceps dobra o cotovelo, pra puxar e levantar peso.", "destaque": ["Bíceps"], "explodir": True},
        {"fala": "O abdômen, o famoso tanquinho, segura o tronco e protege os órgãos.", "destaque": ["Abdômen"], "explodir": True},
        {"fala": "Nas costas, os dorsais e o trapézio dão força pra puxar e sustentam a postura.", "destaque": ["Dorsais", "Trapézio"], "explodir": True},
        {"fala": "E na coxa, o quadríceps, um dos músculos mais fortes, estica a perna pra você andar, correr e pular.", "destaque": ["Quadríceps"], "explodir": True},
        {"fala": "Todos juntos é que te deixam mexer: mais de seiscentos músculos puxando os ossos como cordas.",
         "destaque": ["Trapézio", "Peitoral", "Bíceps", "Abdômen", "Dorsais", "Quadríceps"]},
    ],
}

SISTEMA_NERVOSO = {
    "titulo": "O sistema nervoso",
    "zoom": 15,
    "intro": "O sistema nervoso é a fiação do corpo: cérebro, medula e os nervos que correm pra tudo.",
    "partes": [
        {"nome": "Cérebro", "forma": "esfera", "tam": [0.45], "cor": "#ff9bb0", "pos": [0, 2.5, 0], "solido": True, "explode": [0, 0.9, 0.6]},
        {"nome": "Medula espinhal", "forma": "cilindro", "tam": [0.09, 2.6], "cor": "#ffe08a", "pos": [0, 0.9, -0.08], "solido": True, "explode": [1.3, 0, -0.6]},
        {"nome": "Nervos dos braços", "forma": "cilindro", "tam": [0.05, 1.8], "cor": "#ffd45a", "pos": [-0.9, 0.9, 0], "rot": [0, 0, 0.2], "solido": True, "explode": [-1.6, 0, 0.5]},
        {"nome": "Nervo ciático", "forma": "cilindro", "tam": [0.06, 2.1], "cor": "#ffcf3d", "pos": [-0.35, -1.5, 0], "solido": True, "explode": [-0.9, -0.6, 0.5]},
    ],
    "passos": [
        {"fala": "No comando, o cérebro: decide tudo e manda as ordens.", "destaque": ["Cérebro"], "explodir": True},
        {"fala": "Pela coluna desce a medula espinhal, o cabo principal que liga o cérebro ao resto do corpo.", "destaque": ["Medula espinhal"], "explodir": True},
        {"fala": "Dela saem os nervos pros braços, levando o comando de mexer a mão e trazendo de volta o que você sente.", "destaque": ["Nervos dos braços"], "explodir": True},
        {"fala": "E o nervo ciático, o mais grosso do corpo, desce pela perna até o pé. É o que dói na tal da ciática.", "destaque": ["Nervo ciático"], "explodir": True},
        {"fala": "Tudo isso junto manda sinais a quase 400 quilômetros por hora. É a internet do seu corpo.",
         "destaque": ["Cérebro", "Medula espinhal", "Nervos dos braços", "Nervo ciático"]},
    ],
}

CRANIO = {
    "titulo": "O crânio",
    "zoom": 8,
    "intro": "O crânio tem a parte que protege o cérebro, os ossos do rosto e a mandíbula, que abre e fecha.",
    "partes": [
        {"nome": "Calota craniana", "forma": "esfera", "tam": [0.62], "cor": "#ece3d0", "pos": [0, 0.5, 0], "solido": True, "explode": [0, 1.3, 0]},
        {"nome": "Ossos da face", "forma": "caixa", "tam": [0.85, 0.7, 0.7], "cor": "#ded2b8", "pos": [0, -0.15, 0.18], "solido": True, "explode": [0, 0, 1.3]},
        {"nome": "Mandíbula", "forma": "caixa", "tam": [0.75, 0.32, 0.6], "cor": "#e6dcc2", "pos": [0, -0.62, 0.18], "solido": True, "explode": [0, -1.3, 0.7]},
        {"nome": "Órbita esquerda", "forma": "esfera", "tam": [0.16], "cor": "#444", "pos": [-0.24, 0.12, 0.52], "solido": True, "explode": [-0.8, 0.4, 1.0]},
        {"nome": "Órbita direita", "forma": "esfera", "tam": [0.16], "cor": "#444", "pos": [0.24, 0.12, 0.52], "solido": True, "explode": [0.8, 0.4, 1.0]},
    ],
    "passos": [
        {"fala": "Em cima, a calota craniana: o capacete de osso que protege o cérebro.", "destaque": ["Calota craniana"], "explodir": True},
        {"fala": "Na frente, os ossos da face, que dão a forma do rosto e sustentam o nariz e as bochechas.", "destaque": ["Ossos da face"], "explodir": True},
        {"fala": "As órbitas são os buracos onde ficam os olhos, protegidos por osso dos dois lados.", "destaque": ["Órbita esquerda", "Órbita direita"], "explodir": True},
        {"fala": "E a mandíbula é o único osso do crânio que se mexe: é ela que abre e fecha pra você falar e mastigar.", "destaque": ["Mandíbula"], "explodir": True},
        {"fala": "Junto, é o crânio inteiro: proteção pro cérebro em cima e a estrutura do rosto embaixo.",
         "destaque": ["Calota craniana", "Ossos da face", "Mandíbula", "Órbita esquerda", "Órbita direita"]},
    ],
}

# (corpo humano 3D removido a pedido do Rafael em 24/10: tanto o torso.glb oco quanto os órgãos do BodyParts3D
#  ficaram ruins. "corpo humano" sem modelo cai no gerador genérico. As partes avulsas — coração, cérebro,
#  esqueleto etc. — continuam valendo lá embaixo.)

MODELOS = [
    (re.compile(r"camadas?\s+(?:d[ae]|n[ae])\s+(?:terra|planeta)|(?:terra|planeta)\s+por\s+dentro|dentro\s+d[ae]\s+(?:terra|planeta)|"
                r"(?:interior|estrutura|nucleo)\s+d[ae]\s+(?:terra|planeta)"), TERRA),
    (re.compile(r"(?:pecas|partes|componentes|hardware)\s+d[eo]\s+(?:um\s+)?(?:computador|pc)|(?:computador|pc)\s+por\s+dentro|"
                r"dentro\s+d[eo]\s+(?:um\s+)?(?:computador|pc)|montar\s+um\s+(?:computador|pc)"), COMPUTADOR),
    (re.compile(r"\bcoracao\b"), CORACAO),
    (re.compile(r"\bcranio\b|\bcaveira\b|\bmandibula\b|ossos\s+do\s+(?:cranio|rosto|cabeca)"), CRANIO),
    (re.compile(r"\bcerebro\s+humano\b|\bcerebro\b(?!\s+(?:do\s+jarvis|neural))"), CEREBRO),
    (re.compile(r"\besqueleto\b|\bossos?\b|\bossada\b|sistema\s+osseo"), ESQUELETO),
    (re.compile(r"\bmusculos?\b|muscular|musculatura"), MUSCULOS),
    (re.compile(r"sistema\s+nervoso|\bnervos?\b|\bmedula\b|\bneuronal\b"), SISTEMA_NERVOSO),
]

FORMAS = {"esfera", "esfera_cortada", "caixa", "placa", "cilindro", "cone", "toro"}
CORES = ["#4fe3ff", "#ff7a2f", "#ffd23d", "#2ee88a", "#c77dff", "#ff5d8f", "#7cff6b", "#9ad8ff", "#ff9b3d", "#fff6b0"]


def _num(v, padrao, minimo, maximo):
    try:
        return max(minimo, min(maximo, float(v)))
    except (TypeError, ValueError):
        return padrao


def _vet(v, padrao=(0, 0, 0), lim=3.5):
    v = v if isinstance(v, (list, tuple)) else []
    return [_num(v[i] if i < len(v) else padrao[i], padrao[i], -lim, lim) for i in range(3)]


def validar(cena, assunto):
    partes = []
    for i, p in enumerate((cena.get("partes") or [])[:10]):
        if not isinstance(p, dict) or not str(p.get("nome", "")).strip():
            continue
        forma = p.get("forma") if p.get("forma") in FORMAS else "caixa"
        cor = p.get("cor") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(p.get("cor", ""))) else CORES[i % len(CORES)]
        tam = [_num(x, 0.8, 0.04, 3.5) for x in (p.get("tam") or [0.8, 0.8, 0.8])[:3]] or [0.8]
        pos = _vet(p.get("pos"))
        explode = _vet(p.get("explode"), tuple(x * 0.9 for x in pos) if any(pos) else (0, 0.8, 0.6))
        partes.append({"nome": str(p["nome"]).strip()[:40], "forma": forma, "tam": tam, "cor": cor, "pos": pos,
                       "rot": _vet(p.get("rot"), lim=7), "explode": explode, "texto": str(p.get("texto", ""))[:200]})
    if not partes:
        raise ValueError("o modelo não montou peça nenhuma")
    nomes = {p["nome"] for p in partes}
    passos = []
    for s in (cena.get("passos") or [])[:8]:
        if isinstance(s, dict) and str(s.get("fala", "")).strip():
            passos.append({"fala": str(s["fala"]).strip()[:320], "destaque": [n for n in s.get("destaque") or [] if n in nomes],
                           "explodir": bool(s.get("explodir"))})
    if not passos:
        passos = [{"fala": f"{p['nome']}: {p['texto']}" if p["texto"] else p["nome"], "destaque": [p["nome"]], "explodir": True}
                  for p in partes]
    return {"titulo": str(cena.get("titulo") or assunto)[:80], "intro": str(cena.get("intro") or "")[:300],
            "partes": partes, "passos": passos}


PEDIDO = """Você monta apresentações holográficas 3D do J.A.R.V.I.S. (fala com o Rafael, chama ele de chefe, tom leve).
Assunto: "{assunto}".
Monte o objeto com 4 a 9 peças de formas simples e um roteiro de 4 a 7 passos. Responda SÓ este JSON:
{{"titulo": "...", "intro": "1 frase apresentando",
 "partes": [{{"nome": "nome curto em português", "forma": "esfera|esfera_cortada|caixa|placa|cilindro|cone|toro",
   "tam": [..], "pos": [x,y,z], "rot": [rx,ry,rz], "cor": "#rrggbb", "explode": [x,y,z], "texto": "1 frase sobre a peça"}}],
 "passos": [{{"fala": "1 ou 2 frases curtas, faladas", "destaque": ["nome de peça"], "explodir": true|false}}]}}
Regras: tam de esfera = [raio]; caixa/placa = [largura, altura, profundidade]; cilindro/cone = [raio, altura]; toro = [raio, espessura].
Coordenadas entre -2.5 e 2.5, centro em 0,0,0, Y pra cima. Encaixe as peças como no objeto real (uma dentro/em cima da outra).
"explode" = pra onde a peça se afasta quando o objeto se abre (deslocamento, ~1 a 1.8). Cores vivas e diferentes por peça.
Pra coisas com camadas (planeta, célula, olho, átomo) use esfera_cortada uma dentro da outra. Fatos corretos, nada inventado."""


async def montar(assunto):
    t = _sa(assunto)
    for rx, modelo in MODELOS:
        if rx.search(t):
            return json.loads(json.dumps(modelo))
    bruto = await cerebro.completar([{"role": "user", "content": PEDIDO.format(assunto=assunto)}],
                                    json_mode=True, temperatura=0.4, max_tokens=2000, dificil=True)
    return validar(json.loads(bruto[bruto.index("{"):bruto.rindex("}") + 1]), assunto)
