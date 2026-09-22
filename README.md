# vagas-remotas-alerta

Bot que procura **vagas júnior remotas** — e as **presenciais no Rio Grande do
Norte e em Fortaleza** — em onze portais todo dia e avisa no Discord
**apenas as que ainda não foram mostradas**, para candidatar-se sem revisitar
site nenhum.

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

Duas exceções, por motivos diferentes:

- **LinkedIn**: o card de busca daquele portal não traz descrição, então não há
  seções para extrair — e o card não finge ter o que não tem.
- **Mentora Dados**: a descrição existe, mas os termos do portal proíbem
  reproduzir o conteúdo produzido por ele. Ela é usada só para classificar a
  vaga, e o card leva os dados mais as tecnologias que o próprio portal lista.

Isso é uma marca por vaga (`reproduzir_descricao`), não uma regra global.

## Como configurar

**1. Crie o webhook no Discord**

No servidor: Configurações do canal → Integrações → Webhooks → Novo webhook →
copiar a URL.

**2. Guarde a URL como secret no GitHub**

No repositório: Settings → Secrets and variables → Actions → New repository
secret, com o nome `DISCORD_WEBHOOK_URL`.

A URL nunca entra em arquivo do repositório.

**3. Pronto**

O workflow roda sozinho todo dia, às 06:00 (Brasília). Com os nove primeiros
portais, uma execução media 17 minutos, dentro do limite de 30 do workflow —
boa parte é do LinkedIn, que é o portal mais lento. Com os onze, a medição
local deu 20 minutos: LinkedIn 6m30, Solides 3m, Quero Vagas Tech 2m10,
InfoJobs 2m e o Recrutei 50s, em 24 requisições. Para testar antes, dispare
pela aba Actions marcando `dry_run` — ele mostra o que enviaria sem enviar
nada.

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
| `--locais rn fortaleza` | Onde vaga presencial serve (padrão: todos); sem valor = só remotas |
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
| **GeekHunter** | Sitemap e páginas de vaga em HTML, com dados JobPosting |
| **Quero Vagas Tech** | API JSON pública que o front consome, sem autenticação |
| **Mentora Dados** | `admin-ajax` do WordPress, liberado no `robots.txt` — só vagas de dados |
| **Solides** | API JSON pública que o front consome, com filtros nativos de área e nível |
| **InfoJobs** | HTML da busca, renderizado no servidor; paginação por fragmento JSON |
| **Recrutei** | HTML das listagens por caminho; descrição do JSON-LD da página da vaga |

## Mentora Dados: paywall respeitado e descrição fora do card

Portal só de vagas de dados, em WordPress. A listagem chega pelo
`admin-ajax.php`, que o `robots.txt` libera explicitamente, sem login nem nonce.
O filtro de nível funciona no servidor: Júnior + Estágio são ~600 vagas em 12
requisições, em vez de 3.300 em 66. O mesmo endpoint tem ações que **alteram**
dados do site (votar numa vaga, registrar clique); a coleta só chama a de
leitura.

**O paywall é respeitado.** Parte das vagas é travada para assinante, e o
servidor esconde de verdade: a vaga travada chega sem descrição e sem link. Ela
é descartada — e por não entrar no estado de "já avisada", a vaga de acesso
antecipado, que abre para todos à meia-noite, chega numa execução seguinte.

**A descrição não vai para o Discord.** Os termos do site proíbem reproduzir o
conteúdo produzido por eles, e as descrições vêm reescritas no formato do
portal. Ela serve só para classificar a vaga; o card leva título, empresa,
local, modelo, data, as skills que o próprio portal lista e o link. Isso é uma
marca por vaga (`reproduzir_descricao`), então as outras fontes continuam com o
card completo.

Ao contrário do Quero Vagas Tech, **o nível declarado é aproveitado**: em 599
vagas marcadas Júnior/Estágio, nenhuma tinha cargo de nível alto no título.

O que foi medido e precisou de tratamento:

- a data vem como `16/09`, sem ano — completada com o ano mais recente que não
  cai no futuro;
- o local é quase sempre só o estado ("Ceará (CE)"), então **esta fonte não
  prova vaga em Fortaleza**: a capital exige a cidade escrita;
- algumas vagas listam os 27 estados numa string só, que casaria com o
  reconhecedor do RN — viram "Vários estados";
- o link de candidatura às vezes é `#`, e às vezes é um e-mail com `http://`
  colado na frente (`http://dados@empresa.com`), que o Discord recusa. Nos dois
  casos o link vai para a página da vaga no portal, que mostra o e-mail.

Numa coleta real: 599 vagas livres → **27 no funil** (26 remotas e 1 presencial
no RN), e nenhuma delas chegava pelo LinkedIn com os termos atuais. Esse número
merece desconfiança: 95% das vagas do portal vêm do LinkedIn, e ele acrescenta o
nível ao fim de alguns títulos ("…Engenharia de Dados Estágio"), o que impede a
deduplicação por título idêntico.

## Solides: filtros nativos no lugar dos termos de busca

Portal público de um ATS. A API que o front consome é pública e sem
autenticação, e traz a descrição completa já na listagem — não precisa de uma
requisição por vaga, ao contrário da GeekHunter e do Quero Vagas Tech.

Esta é a única fonte que **não usa os treze termos de busca do projeto**: o
portal filtra por área e por nível no servidor, o que entrega o mesmo recorte
com menos requisição e sem depender de casar texto. Só que vários dos filtros
mentem, e cada um foi medido antes de virar código (21/09/2026):

| Parâmetro | O que faz de verdade |
|---|---|
| `occupationAreas=tecnologia` | Recorta a área, com folga: traz "Vendedor Externo" e "Assistente Administrativo" junto |
| `seniorities=junior` | Filtra: 1.103 vagas, contra 3.639 sem filtro |
| `seniorities=estagio` | Devolve **zero** |
| `seniorities=estagiario` / `trainee` / `aprendiz` | Devolvem as 3.639 — igualzinho a `seniorities=ValorInventadoXYZ` |
| `title=<termo>` | Filtra (termo inventado devolve zero), casando palavra inteira |
| `size` | Ignorado: a página é fixa em 10 |

Ou seja, `seniorities` só entende `junior` e ignora o resto em silêncio. Por
isso estágio, trainee e aprendiz entram por `title=`, e `estagio` e
`estagiario` são buscas **separadas** — o casamento é por palavra inteira, e uma
não cobre a outra (113 contra 119 vagas).

**Aqui o nível declarado é aproveitado — o oposto do Quero Vagas Tech.** Em 150
títulos amostrados com `seniorities=junior`, dois traziam marca de nível alto, e
um deles era "Analista Full Stack Júnior / Pleno", título misto que este projeto
aceita de propósito. Nas buscas por `title=`, porém, o campo fica vazio e quem
decide é o título: isso não perde nada (em 50 títulos de `title=estagiario`, o
regex aceitou os 50) e protege do casamento frouxo do parâmetro.

A área vir generosa não é problema — é para isso que existe o portão de
relevância, que descarta o vendedor e o assistente administrativo.

**A listagem vem ordenada por data decrescente, e a coleta para no corte de
idade.** Sem isso seriam 111 páginas de 10 no filtro mais longo; com os 60 dias
padrão são cerca de 48. A ordenação foi conferida página a página, e a cauda
justifica o filtro de idade do projeto: a página 111 traz vagas de 2022.

Duas armadilhas a mais, as duas medidas:

- o `redirectLink` que a API devolve aponta para `{empresa}.solides.jobs`,
  subdomínio que a Solides desativou — cinco de cinco falharam na conexão. O
  link vai para a página canônica do portal, `/vaga/{id}/{slug}`;
- a modalidade vive em `jobType`, não em `homeOffice`: a vaga marcada "remoto"
  veio com `homeOffice` falso.

A busca por local usa `locations`, que quer a **sigla** da UF — `RN` devolve 13
vagas, enquanto `Natal` e `Rio Grande do Norte` devolvem zero. Ela passa na
regra do projeto: `locations=LocalQueNaoExisteXYZ` devolve nada. Como só sabe
pedir o estado, para Fortaleza vem o Ceará inteiro — o que já está tratado, já
que a capital não aceita a consulta como prova e exige a cidade escrita.

## InfoJobs: o `robots.txt` libera, os termos não

O InfoJobs é um dos maiores portais de vagas do país, e a busca dele é
renderizada no servidor — os cards já vêm no HTML, como no Vagas.com. O
`robots.txt` não proíbe nenhum caminho de busca nem as páginas de vaga; o que
ele bloqueia é `/App_WebServices`, `/*.ashx$`, `/candidate`, `/company`,
`/detailvacancy.aspx` e `/Concursos`, e nada disso é usado aqui. Não há
`Crawl-delay` nem `Sitemap:` declarado (`/sitemap.xml` responde 404), então a
descoberta é por busca paginada, e não por sitemap como na GeekHunter.

A coleta foi medida de IP residencial; **do runner do GitHub Actions ainda
não**. Foi assim que a ProgramaThor caiu fora do projeto — 403 a partir de IP
de datacenter —, então vale conferir a primeira execução no workflow.

**Os termos de uso, porém, proíbem mais do que o `robots.txt`.** Em
`/legal/aviso-legal-para-candidatos__15727.aspx` está escrito que "cópias
mediante tecnologias de buscador tipo 'Robot/Crawler' (...) estão expressamente
proibidas" e que "é proibido a reprodução, distribuição, transmissão, adaptação
ou modificação (...) do conteúdo do Portal". É mais forte do que qualquer outra
fonte deste projeto: o Mentora Dados proíbe só reproduzir a descrição. A
escolha aqui foi coletar apenas o que o card já mostra, e nunca republicar o
texto — `reproduzir_descricao=False`, como no Mentora Dados. A descrição ainda
classifica a vaga; o aviso leva título, empresa, local, modalidade, data e
link. **Nenhuma requisição por vaga é feita**: a página de detalhe não é
aberta, o que mantém a coleta inteira em 57 requisições.

Cada parâmetro foi medido antes de virar código (22/09/2026):

| URL | O que faz de verdade |
|---|---|
| `/vagas-de-emprego-<termo>.aspx` | Listagem geral: "python" devolve 233 vagas |
| `/vagas-de-emprego-<termo>-trabalho-home-office.aspx` | **Só remotas**: as mesmas 233 viram 70. É a única listagem de modalidade que o site marca `rel="follow"` |
| `/vagas-de-emprego-<termo>-em-<cidade>,-<uf>.aspx` | Por cidade, **com a vírgula literal**: `/empregos-em-natal,-rn.aspx` devolve 2.130 vagas; `fortaleza,-ce`, 3.061 |
| `/empregos-em-natal.aspx` (sem a UF) | **200 e redireciona para São Paulo**, igual a `cidadequenaoexistexyz,-rn` |
| `?page=2` na página HTML | Ignorado — devolve a mesma primeira vaga; testadas onze variantes |
| `/mf-publicarea/VacancyList/GetVacancyListFragment?url=…&page=N` | A paginação real: JSON com `eof` e `listFragmentHTML`, com a mesma marcação de card |

A busca nacional usa só a listagem de home office, que é o que o funil quer e
custa menos: nos treze termos do projeto deu 74 cards na primeira página, e
apenas "estagio desenvolvimento" encheu a página de 20.

**A consulta por cidade não prova o local.** O portal completa a página com
vaga de qualquer canto quando a cidade tem pouco resultado: nos treze termos, `natal,-rn` devolveu 88 cards dos quais
83 não eram de Natal — "Todo Brasil" apareceu 110 vezes e "São Paulo - SP" 28
no total das três cidades. Pior, o portal **conta** essas vagas como resultado
("1 Vaga de Emprego de devops junior em Natal - RN" no cabeçalho) e não as
marca de nenhum jeito: `data-typesimilar` vem vazio tanto nelas quanto nos
acertos. Quem prova o local aqui é o texto do card, que sempre traz cidade e UF
("Natal - RN", "Fortaleza - CE"). Confiar na consulta repetiria o erro do
Trampos, e por isso esta fonte não passa `local_consultado`.

O redirecionamento silencioso é a outra metade do mesmo problema, e é tratado
no código: antes de ler a página, o coletor compara a URL pedida com a que
voltou, e descarta a consulta inteira quando o portal desviou. É isso que
transforma local inválido em zero vaga — a prova que o projeto exige antes de
usar consulta por local em qualquer portal.

Três coisas a mais, as três medidas:

- **a modalidade vem escrita no card**, ao lado do salário e da escolaridade, e
  o InfoJobs distingue as três: em 269 cards, 191 "Home office", 62 "Presencial"
  e 16 "Híbrido". Diferente do Vagas.com, aqui a híbrida é afirmada em vez de
  virar "não informado";
- **o nome da empresa nem sempre é um link** — há link para a página dela
  (`/empresa-grupo-easy__-57056.aspx`), link para a página própria (`/printi`) e
  o texto solto "Empresa confidencial", sem `<a>` nenhum. Ler só o link deixava
  a vaga confidencial sem empresa;
- **a data útil está escondida**. O texto visível é "17 set", sem ano, mas o
  card carrega `data-value="2026/09/17 11:14:00"` num campo oculto. Sem ele
  sobra "Hoje"/"Ontem"; sem os dois a data fica vazia, e a vaga permanece no
  filtro de idade.

Não existe nível "Júnior" no filtro do portal (só Estagiário, Trainee, Analista
e afins), então a senioridade não é declarada pela fonte e quem decide é o
regex — a mesma postura do Quero Vagas Tech.

Uma execução completa da fonte: **405 vagas brutas → 271 de nível de entrada →
61 depois da deduplicação → 9 de tecnologia → 8 no aviso**, em 57 requisições e
cerca de 2 minutos. A queda de 271 para 61 é a mesma vaga aparecendo em vários
termos e nas três cidades. Rodando InfoJobs e Quero Vagas Tech juntos, a
deduplicação removeu as mesmas 210 de quando o InfoJobs roda sozinho: nenhuma
vaga foi colapsada entre os dois portais nessa execução, embora o agregador
também liste InfoJobs.

## Recrutei: o `robots.txt` fecha a busca, os caminhos resolvem

O Recrutei Empregos reúne as vagas publicadas pelas consultorias de R&S que
usam a plataforma Recrutei — acervo que não aparece nos outros dez portais. As
listagens são renderizadas no servidor, como no Vagas.com e no InfoJobs.

**Esta fonte não busca por termo, e quem decidiu isso foi o `robots.txt`.** A
Solides e o Quero Vagas Tech também ignoram os termos, mas por falta de busca
textual na API deles; aqui a busca existe — `GET /busca?keyword=…&city=…` — e o
arquivo bloqueia exatamente essa forma:

```
Disallow: /api/  /recrutest/  /candidato/  /empresa/  /r/knowledge/
Disallow: /*?*keyword=*
Disallow: /*?*q=*
```

O que sobra — e basta — são as listagens por caminho, que não são bloqueadas,
assim como `?page=`, `?model=`, `?setor=` e `?state=`. Por isso o coletor
ignora os treze termos do projeto e varre três caminhos, em vez de fingir uma
busca que o portal proíbe. Cada um foi medido antes de virar código
(22/09/2026):

| URL | O que faz de verdade |
|---|---|
| `/vagas-de-trabalho-remoto-home-office` | **134 vagas em 12 páginas de 12, todas com o selo "Remoto"** — é o `model=remote` do filtro lateral, em caminho limpo |
| `/vagas/em/rn` | 12 vagas, todas de Natal; `?page=2` devolve zero card |
| `/vagas/em/fortaleza-ce` | 43 vagas em 4 páginas, das quais **12 não são de Fortaleza** (7 de Eusébio, 5 de Maracanaú) |
| `/vagas/em/cidade-inventada-xy` | **404** — a consulta por local filtra de verdade |
| `?page=99` | 200 com zero card, sem repetir a primeira página |
| `/vaga/<empresa>/<id>-<slug>` | `JobPosting` em JSON-LD: descrição, `datePosted` com hora, `skills` e `jobLocation` |

Varrer as categorias em vez da listagem de remotas seria desperdício: só
`/vagas/tecnologia` tem 44 páginas, e a taxonomia do portal é barulhenta —
"Atendente - área da saúde" aparece em tecnologia. A listagem de home office
entrega exatamente o que o funil quer, em 12 requisições.

**Os termos de uso, ao contrário dos do InfoJobs, não proíbem nada disso.** São
três páginas e dez cláusulas dirigidas ao candidato — cadastro, bloqueio,
e-mails, foro —, sem uma linha sobre crawler, acesso automatizado ou reprodução
de conteúdo; a cláusula 7 apenas reserva as marcas e a propriedade intelectual
da Recrutei. E a descrição sai do JSON-LD, marcação que o portal publica
justamente para ser sindicada. Por isso aqui a descrição **vai** para o Discord,
no padrão do projeto.

**A descrição é o motivo de esta fonte abrir uma página por vaga.** O card
mostra título, empresa, local, salário, data e selos — e nenhuma descrição.
Isso derruba o portão de relevância: "ENGENHEIRO DE IA JR" é reprovado por
`is_tech` com o título sozinho e aprovado com a descrição, que casa "python",
"postgresql", "backend" e "apis" e a classifica como Backend. Sem abrir a
página, a fonte perderia justamente as vagas que o funil procura. A saída é a
mesma da GeekHunter e do Quero Vagas Tech: pré-filtrar pelo que a listagem já
informa — nível, data, modalidade e local — e só então abrir a página das que
sobraram. Das 189 listadas, sobraram 6.

**A consulta por local filtra, mas mesmo assim não prova o local.** Lugar
inventado responde 404, que é a prova que o projeto exige antes de confiar numa
consulta — diferente do `lc` do Trampos, que não filtra, e do InfoJobs, que
desvia para São Paulo. O que impede confiar nela é outra coisa: a cidade traz a
região metropolitana. Dos 43 cards de `fortaleza-ce`, 12 eram de Eusébio e
Maracanaú. Então `local_consultado` fica vazio, e quem prova o local é o texto
do card, que sempre traz "Cidade, UF, Brasil".

Três coisas a mais, as três medidas:

- **"Presencial ou Remoto" não é remoto.** O portal distingue quatro
  modalidades no próprio filtro (`model=remote`, `presential`,
  `presential-remote`, `hybrid`) e deixa a terceira de fora da listagem de home
  office. O de-para do projeto leria o selo como remoto, só por achar "remoto"
  na string — por isso o coletor traz um de-para explícito, e a vaga entra como
  híbrida;
- **a data vem em texto relativo** ("Publicada há 1 mês", "há 6 dias") e, nas
  primeiras 24 horas, **em horas** — 4 dos 134 cards de remotas. Isso ensinou
  horas e minutos ao normalizador de datas, que já entendia dias, semanas e
  meses. Para as vagas cuja página é aberta, o `datePosted` do JSON-LD
  sobrescreve a estimativa do card com a data exata;
- **o link do card vem com query de rastreio** (`?has_bot=1`,
  `?utm_source=recrutei-empregos-premium`), descartada na hora do parsing: o id
  da vaga está no caminho, e a página responde 200 sem ela.

O portal não declara nível nenhum no card, então a senioridade não vem da fonte
e quem decide é o regex — a mesma postura do InfoJobs e do Quero Vagas Tech.

Uma execução completa da fonte: **189 vagas listadas → 6 candidatas no
pré-filtro → 6 páginas abertas → 1 de tecnologia → 1 no aviso**, em 24
requisições e 50 segundos. A queda de 189 para 6 é o pré-filtro fazendo o que o
pipeline faria depois: o acervo do Recrutei é generalista, e vaga júnior de
tecnologia é a minoria dele.

Rodando com os outros dez portais no mesmo dia, a coleta inteira foi de **4.494
vagas brutas a 163 no aviso**, em 20 minutos. Quanto do acervo do Recrutei os
outros portais já cobrem não foi medido vaga a vaga; o que se sabe do recorte é
que são vagas de consultorias de R&S, e não de páginas de carreira nem dos
agregadores tech que o projeto já lê.

## Quero Vagas Tech, e por que a senioridade dele é ignorada

Este é um agregador: ele mesmo junta vagas de outros lugares. O `robots.txt`
libera tudo (`Allow: /`, sem uma linha de `Disallow`) e a API que o front
consome é pública, então a coleta é direta — listagem paginada e, para cada
vaga, um endpoint com a descrição.

**A senioridade que o portal declara não é aproveitada, e isso é deliberado.**
Numa medição de 741 vagas, 292 vinham marcadas como `Intern` — entre elas
"Gerente de Infraestrutura de TI - LATAM", "Auditor Pleno em Tecnologia" e
"Analista de Produtos de TI Pleno". Isso pesa mais do que parece: o filtro de
nível de entrada deste projeto **respeita** nível declarado pela fonte e nem
consulta o título, justamente porque um campo do portal costuma ser mais
confiável que adivinhação. Aceitar esse campo aqui faria passar gerente e
pleno, então a fonte deixa o campo vazio e quem decide é o título.

A listagem não traz descrição, e o portão de relevância depende dela. Buscar a
descrição das 220 vagas de nível de entrada custaria 220 requisições por
execução; filtrando antes pelo que a listagem já informa — título, data,
modalidade e local — sobram 46. O pré-filtro chama as **mesmas funções** do
pipeline, não cópias: é economia de requisição, nunca regra própria, e o
pipeline reaplica tudo depois.

Vale saber o que ele realmente acrescenta: 395 das 741 vagas vêm do mesmo
portal da Gupy que este projeto já raspa direto, e a deduplicação por
título+empresa colapsa essas. O ganho real é a curadoria manual do site — das
vagas que sobraram no funil, a grande maioria era dela. O InfoJobs e a Solides,
que também alimentam o acervo dele, hoje são coletados direto e não dependem
mais deste caminho.

O envelope da listagem traz `isLimited` e `requiresAuthForMore`. Hoje os dois
vêm `false` para cliente anônimo, mas os campos existem: se um dia começarem a
morder, a coleta avisa em log em vez de silenciosamente trazer dez vagas.

A GeekHunter é coletada de um jeito diferente das demais, e a diferença
vem do `robots.txt` dela:

```
Disallow: /api/
Disallow: /feeds/
```

As superfícies de máquina são proibidas em texto explícito — a técnica usada na
Gupy e no Trampos, de consumir a API JSON que o front chama, está fora de
questão aqui. O mesmo arquivo aponta a superfície pretendida para descoberta: a
página HTML de cada vaga, com dados estruturados JobPosting. Então o caminho é
sitemap → filtro pelo slug → página da vaga, e os dados chegam prontos e
completos: título, empresa, local, data, descrição e modalidade.

O pré-filtro pelo slug usa o **mesmo** `seniority.yml` que filtra títulos mais
adiante — o slug é o título com hífens, e a normalização já troca pontuação por
espaço. Sem isso, seriam 796 páginas por execução em vez de ~50.

A limitação disso é conhecida e vale dizer: o slug só mostra o título. Vaga
júnior anunciada como "Desenvolvedor Front-end", sem marca de nível no título,
passa batido. Buscar as 796 páginas resolveria e levaria uns 26 minutos — mais
que a execução inteira leva hoje.

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

Os números ao lado são de uma execução real (17/09/2026), para dar escala.
Ela é anterior à Solides e ao InfoJobs, então o funil mostra oito portais:

```
coleta nos 8 portais                                            3459
   ↓
filtro de nível de entrada    júnior / estágio / trainee        2405
   ↓
deduplicação                  id do portal, id no link de       1588
                              candidatura, depois título +
                              empresa, aceitando variações
                              do nome ("MV" e "MV Saúde Digital")
   ↓
portão de relevância tech     descarta "Analista Contábil Jr"    922
   ↓
filtro de idade               passou de 60 dias, sai             562
   ↓
filtro de local               remota de qualquer lugar, OU no    132
                              RN, OU em Fortaleza
   ↓
diff com o estado             sobram as que você ainda não viu    54
```

A deduplicação tenta a prova mais forte primeiro. O **id que o link de
candidatura carrega** é mais confiável que o título, porque agregador reescreve
título e nome de empresa mas aponta para a mesma página do ATS. Foi assim que
"DESENVOLVEDOR JÚNIOR" e "Desenvolvedor(a) Júnior – Engenharia / Projetos
Técnicos" se revelaram a mesma vaga da BMP: mesmo UUID no link. Em 1.466 vagas
reais de três fontes, essa regra pegou 8 duplicatas que as regras de título não
pegavam.

Id é reconhecido em quatro formas, todas medidas nos links das fontes: UUID
(`inhire.app/vagas/53e6e9da-…`), sequência de 7 ou mais dígitos
(`linkedin.com/jobs/view/4464615185`), segmento só de dígitos
(`totvs.app/vempratotvs/11639`) e token com dígito
(`gupy.io/job/eyJqb2JJZCI6…`). Slug de título **não** vale como id: seria igual
em duas empresas do mesmo portal. E token precisa ter dígito — sem isso,
`carreiratotvslinx` juntava três vagas diferentes da Linx e
`CandidateExperience`, caminho fixo do Oracle Recruiting, juntava seis de
empresas diferentes.

O filtro de idade existe porque portal não tira anúncio velho do ar: numa
coleta real vieram vagas de 2022, de painel de carreira já desativado. Vaga
**sem** data informada fica — não dá para provar que é velha. É o oposto do
filtro de remotas, onde a falta de informação derruba a vaga: ali o silêncio
esconderia uma presencial, aqui esconderia só a idade.

Só o Vagas.com não publica a data em ISO — ele mistura `03/08/2026` com texto
relativo (`Há 5 dias`, `Hoje`), convertido na coleta. `Há mais de 30 dias` vira
exatamente 30: é o piso que o portal garante, e arredondar para mais inventaria
idade que ele não afirma.

## Presencial no Rio Grande do Norte e em Fortaleza

Além das remotas de qualquer lugar, entram as vagas do **RN inteiro** e da
**capital, Fortaleza (CE)**, sem a região metropolitana. Vale qualquer
modalidade — presencial, híbrida ou não informada. Aqui o **local** é a prova,
e a modalidade não precisa ser afirmada: se dá para ir até lá, serve.

Isso exige **buscar** por localização, não só filtrar: numa coleta com as
buscas nacionais, das 364 vagas encontradas exatamente **1** era do RN. Cada
portal quer a localização num formato próprio, e todos foram medidos contra a
API antes de virar código:

| Portal | RN (estado) | Fortaleza (cidade) |
|---|---|---|
| **Gupy** | `state=Rio Grande do Norte` — por extenso; `RN` devolve zero | `city=Fortaleza` |
| **LinkedIn** | `geoId=104863467` | `geoId=103836099` — cobre a região metropolitana; só vale o texto |
| **Vagas.com** | `/vagas-em-natal-rn` | `/vagas-em-fortaleza-ce` — **com** a UF |
| **Trampos** | fica de fora (ver abaixo) | fica de fora |
| **We Work Remotely** | fica de fora — feed de vagas remotas globais | fica de fora |
| **Solides** | `locations=RN` — a sigla; o nome por extenso devolve zero | `locations=CE` — só sabe pedir a UF; só vale o texto |
| **InfoJobs** | `/…-em-natal,-rn` e `/…-em-mossoro,-rn` — **com** a UF e a vírgula | `/…-em-fortaleza,-ce` — só vale o texto |
| **Recrutei** | `/vagas/em/rn` — a UF sozinha cobre Natal e Mossoró | `/vagas/em/fortaleza-ce` — traz Eusébio e Maracanaú; só vale o texto |

Estado e cidade não se pedem do mesmo jeito, e a diferença importa. No RN, vaga
que vem de uma consulta por local é aceita **pela consulta** — então pedir
`state=Ceará` e filtrar Fortaleza depois deixaria passar Caucaia e Juazeiro do
Norte. No Vagas.com, `/vagas-em-fortaleza-ce` trouxe 11 de 11 em Fortaleza;
sem o `-ce`, vieram São Paulo, Recife e "Brasil" misturados.

Em Fortaleza a consulta **não** basta, porque o pedido é só a capital e o geoId
do LinkedIn cobre a região metropolitana: numa coleta real, trouxe duas vagas
de Maracanaú e uma de Eusébio. Por isso Fortaleza exige a cidade escrita no
local da vaga. Na mesma coleta isso tirou exatamente essas três e manteve as
26 da capital.

A busca por local repete **os mesmos termos** da busca nacional, e isso não é
detalhe. Consultar o estado inteiro sem termo foi tentado primeiro e trouxe
"Estagiário de Manutenção Industrial" — o portão de relevância o aceitou porque
a descrição cita Excel e SAP. Com os termos, a consulta por local tem a mesma
precisão da nacional.

### O Trampos saiu das consultas por local — era um erro

O parâmetro `lc` da API do Trampos **muda** o resultado, mas não filtra pelo
local pedido:

```
tr=desenvolvedor&lc=Natal                   -> vaga 772281
tr=desenvolvedor&lc=Fortaleza               -> vaga 772281
tr=desenvolvedor&lc=CidadeQueNaoExisteXYZ   -> vaga 772281
```

Quando o RN foi implementado, "7 vagas viram 2" foi lido como filtro
funcionando. Como a listagem do Trampos não traz cidade, a vaga era aceita só
por ter vindo da consulta — ou seja, vaga de qualquer lugar podia chegar como
"do RN". O teste com um local inventado só foi feito ao adicionar Fortaleza.
Agora o Trampos contribui apenas com vagas remotas.

**Regra para qualquer local novo:** só usar a consulta de um portal depois de
provar que um local inventado devolve nada.

### Reconhecer o local no texto

No RN o reconhecimento aceita `RN`, `Rio Grande do Norte`, `Natal` e `Mossoró`.
Cidade homônima ficou de fora de propósito — `Parnamirim` também é município de
Pernambuco, e `Santa Cruz` existe em vários estados. As outras cidades do RN
entram mesmo assim, porque os portais escrevem o estado junto.

Em Fortaleza o nome sozinho não basta: existem **Fortaleza dos Valos** (RS),
**Fortaleza de Minas** (MG), **Fortaleza dos Nogueiras** (MA) e **Cruzeiro da
Fortaleza** (MG). Então só conta "Fortaleza" com o Ceará junto — que é como
todos os portais medidos escrevem ("Fortaleza, Ceará", "Fortaleza / CE"). Uma
vaga que diga só "Fortaleza", sem estado, fica de fora: não dá para saber qual
é. "Greater Fortaleza", do LinkedIn, também fica: é o rótulo da região
metropolitana inteira, e não prova que a vaga é na capital.

O filtro de remotas descarta vagas sem modalidade informada: *"não informado"
não é prova de remoto. Isso corta bastante — o LinkedIn e o Vagas.com não
distinguem presencial de híbrido no card de listagem.

As regras de classificação ficam em três YAMLs comentados
(`scraper/rules/`), editáveis sem tocar em Python.

## Testes

```bash
python -m pytest -q
```

São 468 testes e nenhum acessa a rede: os parsers são testados contra respostas
reais capturadas dos portais, guardadas dentro dos próprios testes.

---

## Origem

O código de coleta e classificação vem do
[vagas-tech-junior](https://github.com/EmidioLP/vagas-tech-junior), um projeto
de análise que responde "qual área de tecnologia mais contrata júnior no
Brasil". Aquele gera CSVs, gráficos e uma API; este aqui é o oposto — não
guarda histórico nem publica nada, só avisa o que apareceu de novo.

---

## Licença

[MIT](LICENSE) — use, modifique e redistribua à vontade, mantendo o aviso de
copyright.

A licença cobre **o código deste repositório**, não as vagas coletadas. Elas
pertencem aos portais e às empresas que as publicaram, e raspá-las está sujeito
aos termos de uso de cada site, que a licença não altera.

Nenhuma vaga é versionada aqui: o `state/vagas_vistas.json` guarda só os
identificadores das que já foram avisadas (`fonte:id`), sem título, empresa nem
descrição.
