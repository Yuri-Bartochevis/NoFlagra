"""Long-form legal copy for /privacidade and /termos, in PT and EN.

Kept out of i18n.py on purpose: that file is a flat key -> string map for
interface strings, and multi-paragraph legal text would swamp it. Here the
unit is a page: a title, an "last updated" date, a lead paragraph, and an
ordered list of (heading, [paragraphs]) sections that legal.html walks.

    IMPORTANT — this is a first draft written from how the system actually
    behaves, not advice from a lawyer. It describes real data flows
    (continuous local recording, clips uploaded to S3, one library per gym)
    so that a lawyer has something concrete to correct rather than a blank
    page. Have it reviewed before selling to a gym you don't own.

Both pages render a visible "under review" notice for the same reason —
see LEGAL_DRAFT_NOTICE below.
"""

# Bumped by hand whenever the text below changes materially.
LAST_UPDATED = "2 de agosto de 2026"
LAST_UPDATED_EN = "2 August 2026"

# Where data subject / LGPD requests land. Split out so it's changed in one
# place once there's a dedicated address (encarregado@ rather than hello@).
DPO_EMAIL = "hello@noflagra.app"


LEGAL_DRAFT_NOTICE = {
    "pt": (
        "Esta é uma versão preliminar, escrita a partir do funcionamento real "
        "do sistema e ainda em revisão jurídica. Se sua academia precisa de um "
        "contrato ou de um acordo de tratamento de dados assinado, fale com a "
        "gente — a gente manda a versão atual."
    ),
    "en": (
        "This is a preliminary version, written from how the system actually "
        "works and still under legal review. If your gym needs a signed "
        "contract or data processing agreement, get in touch and we'll send "
        "the current version."
    ),
}


PRIVACY = {
    "pt": {
        "title": "Política de Privacidade",
        "updated": LAST_UPDATED,
        "lead": (
            "O NO FLAGRA grava vídeo de pessoas treinando. Isso é dado pessoal, "
            "e a gente trata isso com a seriedade que a LGPD (Lei 13.709/2018) "
            "exige. Esta página explica, sem juridiquês, o que é coletado, "
            "quem consegue ver, por quanto tempo fica guardado e como pedir "
            "exclusão."
        ),
        "sections": [
            (
                "Quem é responsável pelos dados",
                [
                    "A academia que contrata o NO FLAGRA é a <b>controladora</b> "
                    "dos dados: é ela quem decide instalar as câmeras, quem "
                    "aparece no tatame e quem tem login para assistir aos clipes.",
                    "O NO FLAGRA é <b>operador</b>: a gente fornece o "
                    "equipamento e o software e trata os dados seguindo as "
                    "instruções da academia. A gente não vende, não licencia e "
                    "não usa o vídeo da sua academia para nenhuma finalidade "
                    "própria — nem para treinar modelos, nem para marketing, "
                    "salvo autorização escrita e específica.",
                    "Na prática isso significa que a academia precisa informar "
                    "seus alunos de que o tatame é filmado. A gente fornece um "
                    "aviso pronto para afixar na recepção e no tatame.",
                ],
            ),
            (
                "O que é coletado",
                [
                    "<b>Dados de conta:</b> nome, email e senha (guardada como "
                    "hash, nunca em texto puro) de cada pessoa com login, além "
                    "do nome da academia e do papel de cada usuário "
                    "(administrador ou membro).",
                    "<b>Vídeo:</b> a câmera grava o tatame de forma contínua, "
                    "em um gravador que fica dentro da própria academia. Essa "
                    "gravação contínua <b>não sai da academia</b>. Só sobe para "
                    "a nuvem o trecho de 10 minutos que alguém salvou "
                    "apertando o botão.",
                    "<b>Metadados do clipe:</b> data, hora, duração, tamanho do "
                    "arquivo, e a qual câmera e academia ele pertence.",
                    "<b>Dados técnicos:</b> registros de acesso ao painel "
                    "(data, hora e endereço IP), necessários por segurança e "
                    "exigidos pelo Marco Civil da Internet.",
                ],
            ),
            (
                "Cookies",
                [
                    "A gente usa o mínimo: um cookie de sessão, que mantém "
                    "você logado, e um cookie <code>lang</code>, que lembra se "
                    "você prefere português ou inglês. Não há cookies de "
                    "publicidade nem rastreamento de terceiros no site."
                ],
            ),
            (
                "Quem consegue ver os clipes",
                [
                    "Só quem a academia convidar. Cada academia tem sua própria "
                    "biblioteca, isolada das demais, e o administrador controla "
                    "quem entra e quem sai.",
                    "A equipe do NO FLAGRA tem acesso técnico à infraestrutura "
                    "e pode, em tese, acessar arquivos para resolver um "
                    "problema relatado. Esse acesso é excepcional, feito "
                    "mediante solicitação da academia e registrado.",
                ],
            ),
            (
                "Onde os dados ficam e com quem são compartilhados",
                [
                    "Os clipes salvos ficam em armazenamento de objetos na "
                    "nuvem (Amazon S3) e os dados de conta em um banco "
                    "PostgreSQL gerenciado. Hoje esses serviços rodam fora do "
                    "Brasil, o que a LGPD permite mediante salvaguardas "
                    "contratuais.",
                    "A gente não compartilha dados com anunciantes, "
                    "corretores de dados ou parceiros comerciais. "
                    "Compartilhamento só acontece com os provedores de "
                    "infraestrutura acima, ou por ordem judicial.",
                ],
            ),
            (
                "Por quanto tempo fica guardado",
                [
                    "A gravação contínua no gravador local é sobrescrita "
                    "automaticamente conforme o disco enche — normalmente "
                    "poucos dias.",
                    "Os clipes salvos ficam na biblioteca da academia até "
                    "serem apagados pelo administrador ou até o fim do "
                    "contrato. Encerrado o contrato, a academia tem 30 dias "
                    "para baixar o que quiser guardar; depois disso os "
                    "arquivos são excluídos.",
                    "Dados de conta são excluídos junto com o encerramento, "
                    "salvo o que a gente precise reter por obrigação legal.",
                ],
            ),
            (
                "Seus direitos",
                [
                    "A LGPD garante a você confirmar se tratamos seus dados, "
                    "acessá-los, corrigi-los, pedir anonimização ou exclusão, "
                    "revogar consentimento e solicitar portabilidade.",
                    "Se você treina em uma academia que usa NO FLAGRA, o "
                    "caminho mais rápido é falar com a própria academia, que é "
                    "a controladora. Se preferir, escreva para "
                    f"<a href=\"mailto:{DPO_EMAIL}\">{DPO_EMAIL}</a> e a gente "
                    "encaminha e acompanha o pedido.",
                    "Pedidos de exclusão de um clipe específico em que você "
                    "aparece são atendidos — informe a data e o horário "
                    "aproximado.",
                ],
            ),
            (
                "Segurança",
                [
                    "Senhas são guardadas como hash. Cada gravador é pareado "
                    "com uma chave própria, guardada em hash no servidor — não "
                    "existe segredo único compartilhado entre academias. O "
                    "gravador nunca guarda credenciais de nuvem: ele recebe "
                    "URLs temporárias para enviar cada clipe.",
                    "Nenhum sistema é imune a incidentes. Em caso de "
                    "vazamento que traga risco relevante, a gente comunica as "
                    "academias afetadas e a ANPD, como manda a lei.",
                ],
            ),
            (
                "Contato",
                [
                    "Dúvidas sobre privacidade, ou para exercer qualquer um "
                    "dos direitos acima: "
                    f"<a href=\"mailto:{DPO_EMAIL}\">{DPO_EMAIL}</a>."
                ],
            ),
        ],
    },
    "en": {
        "title": "Privacy Policy",
        "updated": LAST_UPDATED_EN,
        "lead": (
            "NO FLAGRA records video of people training. That is personal "
            "data, and we treat it with the seriousness Brazil's LGPD (Law "
            "13.709/2018) requires. This page explains, without legalese, what "
            "is collected, who can see it, how long it is kept, and how to ask "
            "for deletion."
        ),
        "sections": [
            (
                "Who is responsible for the data",
                [
                    "The gym that subscribes to NO FLAGRA is the "
                    "<b>controller</b>: it decides to install the cameras, who "
                    "trains on the mat, and who gets a login to watch clips.",
                    "NO FLAGRA is the <b>operator</b> (processor): we provide "
                    "the hardware and software and process data on the gym's "
                    "instructions. We do not sell, license, or use your gym's "
                    "video for any purpose of our own — not for training "
                    "models, not for marketing — absent specific written "
                    "permission.",
                    "In practice this means the gym must tell its members the "
                    "mat is filmed. We provide a ready-made notice to post at "
                    "reception and at the mat.",
                ],
            ),
            (
                "What is collected",
                [
                    "<b>Account data:</b> name, email and password (stored "
                    "hashed, never in plain text) for everyone with a login, "
                    "plus the gym's name and each user's role (admin or "
                    "member).",
                    "<b>Video:</b> the camera records the mat continuously, on "
                    "a recorder that sits inside the gym. That continuous "
                    "recording <b>never leaves the gym</b>. Only the 10-minute "
                    "stretch someone saved by pressing the button is uploaded.",
                    "<b>Clip metadata:</b> date, time, duration, file size, "
                    "and which camera and gym it belongs to.",
                    "<b>Technical data:</b> dashboard access logs (date, time "
                    "and IP address), needed for security and required by "
                    "Brazil's Marco Civil da Internet.",
                ],
            ),
            (
                "Cookies",
                [
                    "We use the minimum: a session cookie that keeps you "
                    "logged in, and a <code>lang</code> cookie remembering "
                    "whether you prefer Portuguese or English. There are no "
                    "advertising cookies and no third-party tracking."
                ],
            ),
            (
                "Who can see the clips",
                [
                    "Only the people the gym invites. Each gym has its own "
                    "library, isolated from every other gym's, and the admin "
                    "controls who gets in and who doesn't.",
                    "The NO FLAGRA team has technical access to the "
                    "infrastructure and could in principle open a file to "
                    "resolve a reported problem. Such access is exceptional, "
                    "happens at the gym's request, and is logged.",
                ],
            ),
            (
                "Where data lives and who it is shared with",
                [
                    "Saved clips live in cloud object storage (Amazon S3) and "
                    "account data in a managed PostgreSQL database. Today "
                    "those services run outside Brazil, which the LGPD permits "
                    "subject to contractual safeguards.",
                    "We do not share data with advertisers, data brokers, or "
                    "commercial partners. Sharing happens only with the "
                    "infrastructure providers above, or under a court order.",
                ],
            ),
            (
                "How long it is kept",
                [
                    "The continuous recording on the local recorder is "
                    "overwritten automatically as the disk fills — typically "
                    "within days.",
                    "Saved clips stay in the gym's library until an admin "
                    "deletes them or the contract ends. On termination the gym "
                    "has 30 days to download whatever it wants to keep; after "
                    "that the files are deleted.",
                    "Account data is deleted along with it, except what we are "
                    "legally required to retain.",
                ],
            ),
            (
                "Your rights",
                [
                    "The LGPD gives you the right to confirm whether we "
                    "process your data, access it, correct it, request "
                    "anonymisation or deletion, withdraw consent, and request "
                    "portability.",
                    "If you train at a gym that uses NO FLAGRA, the fastest "
                    "route is to ask the gym itself, which is the controller. "
                    "If you'd rather, write to "
                    f"<a href=\"mailto:{DPO_EMAIL}\">{DPO_EMAIL}</a> and we'll "
                    "forward and follow up on the request.",
                    "Requests to delete a specific clip you appear in are "
                    "honoured — tell us the date and approximate time.",
                ],
            ),
            (
                "Security",
                [
                    "Passwords are stored hashed. Each recorder is paired with "
                    "its own key, stored hashed on the server — there is no "
                    "single shared secret across gyms. The recorder never "
                    "holds cloud credentials: it receives short-lived URLs to "
                    "upload each clip.",
                    "No system is immune to incidents. In the event of a "
                    "breach posing meaningful risk, we notify the affected "
                    "gyms and the ANPD, as the law requires.",
                ],
            ),
            (
                "Contact",
                [
                    "Privacy questions, or to exercise any of the rights "
                    "above: "
                    f"<a href=\"mailto:{DPO_EMAIL}\">{DPO_EMAIL}</a>."
                ],
            ),
        ],
    },
}


TERMS = {
    "pt": {
        "title": "Termos de Uso",
        "updated": LAST_UPDATED,
        "lead": (
            "O NO FLAGRA é vendido como uma instalação única mais uma "
            "mensalidade. Estes termos explicam o que está incluído, o que é "
            "responsabilidade de cada lado e como encerrar."
        ),
        "sections": [
            (
                "O que está incluído",
                [
                    "A instalação cobre câmera, suporte e fonte, botão sem fio "
                    "no tatame, gravador local instalado, cabeamento, "
                    "configuração, visita técnica e treinamento da equipe. O "
                    "valor é orçado por academia, porque depende do número de "
                    "tatames e do cabeamento do local. A visita para orçamento "
                    "é gratuita.",
                    "A mensalidade, a partir de R$ 150 por câmera, cobre a "
                    "biblioteca de clipes na nuvem, logins ilimitados para a "
                    "equipe, atualizações de software e suporte.",
                ],
            ),
            (
                "Equipamento",
                [
                    "O equipamento instalado pertence à academia após o "
                    "pagamento da instalação.",
                    "Defeito de fabricação ou falha do equipamento em uso "
                    "normal é substituído sem custo nos primeiros 12 meses. "
                    "Dano por queda, líquido, surto elétrico, furto ou uso "
                    "fora do previsto não está coberto.",
                    "A academia fornece energia e rede no ponto de "
                    "instalação e mantém o gravador ligado.",
                ],
            ),
            (
                "Responsabilidades da academia",
                [
                    "Informar alunos e visitantes de que o tatame é filmado, "
                    "afixando o aviso que a gente fornece.",
                    "Controlar quem tem login para a biblioteca de clipes e "
                    "remover o acesso de quem sai da equipe.",
                    "Não usar o sistema para vigiar funcionários fora da "
                    "finalidade de treino, nem instalar câmera em vestiário, "
                    "banheiro ou qualquer área de privacidade.",
                ],
            ),
            (
                "Disponibilidade",
                [
                    "A gravação e o botão funcionam dentro da academia mesmo "
                    "sem internet — essa é uma decisão de projeto, não um "
                    "acaso. Se a conexão cair, os clipes salvos sobem sozinhos "
                    "quando ela voltar.",
                    "O painel na nuvem é fornecido no estado em que se "
                    "encontra, com esforço razoável de disponibilidade, mas "
                    "sem SLA contratado nesta fase do produto.",
                ],
            ),
            (
                "Pagamento e cancelamento",
                [
                    "A instalação é paga uma vez, com possibilidade de "
                    "parcelamento. A mensalidade é cobrada mês a mês.",
                    "Não há fidelidade: a academia pode cancelar quando "
                    "quiser, e a cobrança cessa no fim do ciclo vigente. Não "
                    "há reembolso proporcional de mês já iniciado.",
                    "Cancelado o serviço, a academia tem 30 dias para baixar "
                    "os clipes que quiser guardar antes da exclusão.",
                ],
            ),
            (
                "Limite de responsabilidade",
                [
                    "A gente faz o sistema gravar de forma contínua justamente "
                    "para que o momento já esteja salvo antes de alguém "
                    "pensar em filmar. Ainda assim, falha de equipamento, "
                    "queda de energia ou erro de operação podem fazer um clipe "
                    "não existir.",
                    "A responsabilidade do NO FLAGRA fica limitada ao valor "
                    "pago pela academia nos 12 meses anteriores ao evento. A "
                    "gente não responde por perda de oportunidade decorrente "
                    "de um clipe que não foi gravado.",
                ],
            ),
            (
                "Foro e alterações",
                [
                    "Estes termos são regidos pela lei brasileira.",
                    "Mudanças materiais são comunicadas por email às "
                    "academias contratantes com pelo menos 30 dias de "
                    "antecedência.",
                ],
            ),
        ],
    },
    "en": {
        "title": "Terms of Service",
        "updated": LAST_UPDATED_EN,
        "lead": (
            "NO FLAGRA is sold as a one-time installation plus a monthly fee. "
            "These terms set out what is included, what each side is "
            "responsible for, and how to end it."
        ),
        "sections": [
            (
                "What's included",
                [
                    "Installation covers camera, mount and power supply, the "
                    "wireless mat button, the local recorder installed, "
                    "cabling, configuration, the on-site visit and team "
                    "training. It is quoted per gym, because it depends on how "
                    "many mats you have and on your cabling. The quoting visit "
                    "is free.",
                    "The monthly fee, starting at R$150 per camera, covers the "
                    "cloud clip library, unlimited logins for your team, "
                    "software updates and support.",
                ],
            ),
            (
                "Hardware",
                [
                    "Installed hardware belongs to the gym once installation "
                    "is paid.",
                    "Manufacturing defects or failure under normal use are "
                    "replaced free of charge for the first 12 months. Damage "
                    "from drops, liquid, power surges, theft or use outside "
                    "the intended purpose is not covered.",
                    "The gym provides power and network at the installation "
                    "point and keeps the recorder switched on.",
                ],
            ),
            (
                "The gym's responsibilities",
                [
                    "Tell members and visitors that the mat is filmed, by "
                    "posting the notice we provide.",
                    "Control who has a login to the clip library, and remove "
                    "access for people who leave.",
                    "Not use the system to monitor staff outside the training "
                    "purpose, and never install a camera in a changing room, "
                    "bathroom, or any area with an expectation of privacy.",
                ],
            ),
            (
                "Availability",
                [
                    "Recording and the button keep working inside the gym even "
                    "with no internet — that is a design decision, not an "
                    "accident. If the connection drops, saved clips upload on "
                    "their own once it returns.",
                    "The cloud dashboard is provided as-is, with reasonable "
                    "effort toward availability, but without a contracted SLA "
                    "at this stage of the product.",
                ],
            ),
            (
                "Payment and cancellation",
                [
                    "Installation is paid once, with instalment plans "
                    "available. The monthly fee is billed month to month.",
                    "There is no lock-in: the gym may cancel at any time and "
                    "billing stops at the end of the current cycle. Started "
                    "months are not pro-rated.",
                    "On cancellation the gym has 30 days to download any clips "
                    "it wants to keep before deletion.",
                ],
            ),
            (
                "Limitation of liability",
                [
                    "The system records continuously precisely so the moment "
                    "is already saved before anyone thinks to hit record. Even "
                    "so, hardware failure, power loss or operator error can "
                    "mean a clip does not exist.",
                    "NO FLAGRA's liability is limited to the amount the gym "
                    "paid in the 12 months preceding the event. We are not "
                    "liable for lost opportunity arising from a clip that was "
                    "not recorded.",
                ],
            ),
            (
                "Governing law and changes",
                [
                    "These terms are governed by Brazilian law.",
                    "Material changes are communicated by email to subscribing "
                    "gyms at least 30 days in advance.",
                ],
            ),
        ],
    },
}
