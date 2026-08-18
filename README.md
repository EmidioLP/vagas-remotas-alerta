# vagas-remotas-alerta

Bot que procura **vagas júnior remotas** em cinco portais a cada três dias e
avisa no Discord **apenas as que ainda não foram mostradas** — para candidatar-se
sem precisar revisitar site nenhum.

Roda sozinho no GitHub Actions. Não precisa de servidor.

---

## O que chega no Discord

Cada vaga vira um card com:

- **Título linkado** direto para a vaga no portal
- **Empresa**, **modalidade**, **nível**, **área**, **local**, **data de publicação**
- **Todas as tecnologias** identificadas na vaga
- **Requisitos**, **Responsabilidades** e **Benefícios**, recortados da descrição

Requisitos e benefícios não são campos estruturados em portal nenhum — vivem
soltos no texto. O bot os recorta pelos títulos de seção que os portais usam
("Requisitos e qualificações", "Benefícios", "Informações adicionais"). Numa
coleta real da Gupy: requisitos e responsabilidades em 12 de 12 vagas,
benefícios em 6 de 12.

Vagas do LinkedIn chegam só com os metadados: o card de busca daquele portal não
traz descrição, então não há seções para extrair — e o card não finge ter o que
não tem.

## Como configurar

**1. Crie o webhook no Discord**

No servidor: Configurações do canal → Integrações → Webhooks → Novo webhook →
copiar a URL.

**2. Guarde a URL como secret no GitHub**

No repositório: Settings → Secrets and variables → Actions → New repository
secret, com o nome `DISCORD_WEBHOOK_URL`.

A URL nunca entra em arquivo do repositório.

**3. Pronto**

O workflow roda sozinho a cada três dias, às 06:00 (Brasília). Para testar
antes, dispare pela aba Actions marcando `dry_run` — ele mostra o que enviaria
sem enviar nada.

## Rodando na sua máquina

```bash
pip install -r requirements.txt
```

```bash
python alerta.py --dry-run
```

Para enviar de verdade, defina o webhook no ambiente antes:

```bash
python alerta.py
```

### Opções

| Flag | Efeito |
|------|--------|
| `--dry-run` | Mostra as vagas novas sem enviar nem gravar estado |
| `--sources gupy linkedin` | Escolhe os portais |
| `--terms "..." "..."` | Substitui os termos de busca |
| `--dias N` | Idade máxima da vaga, em dias (padrão 60; `0` desliga) |
| `--todas-modalidades` | Não filtra por remoto |
| `--max-pages N` | Páginas por termo, por portal (padrão 5) |
| `--delay S` | Segundos entre requisições (padrão 2) |
| `-v` | Log detalhado |

---

## Fontes

| Portal | Como é acessado |
|---|---|
| **Gupy** | Endpoint JSON público que o front do portal usa |
| **Vagas.com.br** | HTML da busca, renderizado no servidor |
| **LinkedIn Jobs** | API de convidado, sem login (`geoId` do Brasil) |
| **Trampos.co** | API JSON pública que a SPA consome |
| **We Work Remotely** | Feeds RSS por categoria (vagas globais) |

Três portais ficaram de fora, e o motivo importa:

- **Indeed** e **Catho** respondem `403` a qualquer cliente que não seja um
  navegador real — bloqueio de bot no edge, não questão de JavaScript.
- **ProgramaThor** funciona de um IP residencial, mas responde `403` a partir de
  IP de datacenter. Como este projeto roda no GitHub Actions, ela não entra.

Essa diferença foi **medida**, não suposta: um workflow de sondagem consultou os
portais de dentro de um runner e mostrou quais respondem de lá. Gupy, Vagas.com,
LinkedIn, Trampos e WWR passaram sem problema.

## Como ele sabe o que já mostrou

O runner do GitHub Actions é descartado ao terminar, então o estado vive em
`state/vagas_vistas.json`, versionado, e o próprio workflow faz commit dele de
volta. A chave é o par `fonte:id` — a mesma identidade que a deduplicação trata
como definitiva.

Duas decisões de segurança, ambas com teste:

- **Sem `DISCORD_WEBHOOK_URL`, o estado não é gravado.** Marcar como avisada uma
  vaga que ninguém viu a faria sumir para sempre.
- **O envio para no primeiro erro** (rate limit, webhook revogado) e o estado
  fica intacto, pelo mesmo motivo.

## Como uma vaga é selecionada

```
coleta nos 5 portais
   ↓
filtro de nível de entrada    → júnior / estágio / trainee / aprendiz
   ↓
deduplicação                  → por id do portal, depois por título+empresa
   ↓
portão de relevância tech     → descarta "Analista Contábil Jr" e afins
   ↓
filtro de idade               → descarta o que passou de 60 dias
   ↓
filtro de remotas             → só o que o portal AFIRMA ser remoto
   ↓
diff com o estado             → sobram as que você ainda não viu
```

O filtro de idade existe porque portal não tira anúncio velho do ar: numa
coleta real vieram vagas de 2022, de painel de carreira já desativado. Vaga
**sem** data informada fica — não dá para provar que é velha. É o oposto do
filtro de remotas, onde a falta de informação derruba a vaga: ali o silêncio
esconderia uma presencial, aqui esconderia só a idade.

Só o Vagas.com não publica a data em ISO — ele mistura `03/08/2026` com texto
relativo (`Há 5 dias`, `Hoje`), convertido na coleta. `Há mais de 30 dias` vira
exatamente 30: é o piso que o portal garante, e arredondar para mais inventaria
idade que ele não afirma.

O filtro de remotas descarta vagas sem modalidade informada: *"não informado"
não é prova de remoto. Isso corta bastante — o LinkedIn e o Vagas.com não
distinguem presencial de híbrido no card de listagem.

As regras de classificação ficam em três YAMLs comentados
(`scraper/rules/`), editáveis sem tocar em Python.

## Testes

```bash
python -m pytest -q
```

São 150 testes e nenhum acessa a rede: os parsers são testados contra respostas
reais capturadas dos portais.

---

## Origem

O código de coleta e classificação vem do
[vagas-tech-junior](https://github.com/EmidioLP/vagas-tech-junior), um projeto
de análise que responde "qual área de tecnologia mais contrata júnior no
Brasil". Aquele gera CSVs, gráficos e uma API; este aqui é o oposto — não
guarda histórico nem publica nada, só avisa o que apareceu de novo.
