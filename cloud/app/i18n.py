from flask import request

DEFAULT_LOCALE = "pt"
LOCALES = ("pt", "en")

TRANSLATIONS = {
    "pt": {
        "nav_login": "Entrar",
        "nav_dashboard": "Painel",
        "nav_logout": "Sair",
        "nav_start_gym": "Comece sua academia",
        "hero_h1": "Nunca perca o momento.",
        "hero_p": (
            "Aperte um botão do lado do tatame. Receba os últimos 10 minutos, "
            "cortados da gravação contínua e prontos pra assistir — antes de "
            "você nem sair do tatame."
        ),
        "eyebrow_how": "Como funciona",
        "step1_h": "Aperte",
        "step1_p": "Um botão do lado do tatame. Sem cameraman, sem procurar o celular no meio do rolo.",
        "step2_h": "Corta",
        "step2_p": "A câmera já estava gravando — o botão só corta os últimos 10 minutos dela.",
        "step3_h": "Revê",
        "step3_p": "O clipe aparece na biblioteca da sua academia, pronto pra assistir no celular em segundos.",
        "step4_h": "Compartilha",
        "step4_p": "Manda pro seu parceiro de treino, pro professor, ou guarda pra próxima revisão de faixa.",
        "eyebrow_why": "Por que as academias usam",
        "benefit1_h": "Nunca perde uma finalização",
        "benefit1_p": "A câmera nunca para de gravar, então o momento já está salvo antes de alguém pensar em filmar.",
        "benefit2_h": "Um botão, sem operador",
        "benefit2_p": "Qualquer um no tatame pode salvar um clipe no meio do rolo. Ninguém precisa segurar o celular.",
        "benefit3_h": "Um login pra todo mundo",
        "benefit3_p": "Cada aluno da sua academia acessa a mesma biblioteca de clipes — sem celular compartilhado, sem grupo de zap lotado.",
        "benefit4_h": "Um histórico completo",
        "benefit4_p": "Todo clipe salvo fica na nuvem, buscável por dia, pronto sempre que você quiser rever.",
        "showcase_h": "Veja funcionando",
        "showcase_p": (
            "Esse é o painel de verdade que sua academia recebe: visão ao vivo "
            "do tatame, um botão grande, e cada clipe salvo agrupado por dia — "
            "preto e amarelo, feito pra ler do outro lado da sala."
        ),
        "mock_live": "visão ao vivo",
        "cta_band_h": "Pronto pra colocar um no seu tatame?",
        "cta_band_p": "Vai instalar em mais de uma unidade, ou quer falar sobre preço antes?",
        "cta_band_link": "Fala com a gente",
        "nav_pricing": "Preço",
        "nav_get_quote": "Peça um orçamento",
        "hero_note": "Instalação completa na sua academia. Sem cameraman, sem app pra baixar.",
        "hero_cta_secondary": "Ver como funciona",
        "eyebrow_kit": "O que sua academia recebe",
        "kit_h": "Tudo instalado e funcionando.",
        "kit_p": (
            "Você não monta nada e não configura nada. A gente vai até a "
            "academia, instala, testa com a sua equipe e deixa rodando."
        ),
        "kit1_h": "Câmera no tatame",
        "kit1_p": "Câmera fixa com suporte, posicionada pra pegar o tatame inteiro.",
        "kit2_h": "Botão sem fio",
        "kit2_p": "Um botão resistente na beira do tatame. Aperta e pronto.",
        "kit3_h": "Gravador local",
        "kit3_p": "Um computador pequeno que fica na sua academia gravando 24 horas por dia.",
        "kit4_h": "Painel na nuvem",
        "kit4_p": "A biblioteca de clipes que sua equipe acessa pelo celular.",
        "eyebrow_pricing": "Preço",
        "pricing_h": "Uma instalação. Uma mensalidade.",
        "pricing_install_label": "Instalação",
        "pricing_install_value": "sob orçamento",
        "pricing_install_note": "pagamento único · parcelável",
        "pricing_install_1": "Câmera, suporte e fonte",
        "pricing_install_2": "Botão sem fio no tatame",
        "pricing_install_3": "Gravador local instalado",
        "pricing_install_4": "Cabeamento e configuração",
        "pricing_install_5": "Visita, ajuste e treino da equipe",
        "pricing_monthly_label": "Mensalidade",
        "pricing_monthly_value": "R$ 150",
        "pricing_monthly_unit": "por mês, por câmera",
        "pricing_monthly_1": "Biblioteca de clipes na nuvem",
        "pricing_monthly_2": "Logins ilimitados pra sua equipe",
        "pricing_monthly_3": "Atualizações e suporte incluídos",
        "pricing_monthly_4": "Sem fidelidade — cancele quando quiser",
        "pricing_note": (
            "O valor da instalação depende de quantos tatames você tem e do "
            "cabeamento da sua academia. A visita pra orçamento é gratuita."
        ),
        "how_h": "Do tatame pro celular, em 4 passos.",
        "how_p": (
            "A câmera já fica gravando o tempo todo. O botão só marca o que "
            "valeu a pena guardar."
        ),
        "why_h": "Feito pra quem treina, não pra quem filma.",
        "mock_press": "Salvar últimos 10 min",
        "mock_press_sub": "toque no botão do tatame",
        "mock_today": "Hoje",
        "eyebrow_faq": "Dúvidas",
        "faq_h": "Perguntas frequentes",
        "faq1_q": "Preciso de internet rápida?",
        "faq1_a": (
            "Não. A gravação acontece no gravador que fica dentro da sua "
            "academia. A internet só é usada pra subir os clipes que alguém "
            "salvou — nunca o vídeo inteiro do dia."
        ),
        "faq2_q": "E se a internet cair?",
        "faq2_a": (
            "A câmera continua gravando e o botão continua funcionando. "
            "Quando a conexão volta, os clipes salvos sobem pra nuvem sozinhos."
        ),
        "faq3_q": "Quem consegue ver os clipes da minha academia?",
        "faq3_a": (
            "Só quem você convidar. Cada academia tem sua própria biblioteca, "
            "separada das outras, e você controla quem entra e quem sai."
        ),
        "faq4_q": "Funciona com mais de um tatame?",
        "faq4_a": (
            "Sim. Cada tatame ganha sua própria câmera e seu próprio botão, e "
            "todos os clipes caem na mesma biblioteca da academia."
        ),
        "faq5_q": "Alguém precisa ficar operando?",
        "faq5_a": (
            "Não. Não tem cameraman e não tem celular pra segurar. Qualquer "
            "pessoa no tatame aperta o botão no meio do rolo."
        ),
        "faq6_q": "Preciso instalar algum aplicativo?",
        "faq6_a": (
            "Não. Sua equipe entra pelo navegador do celular, com o login da "
            "academia. Funciona em qualquer celular."
        ),
        "contact_h": "Vamos colocar um no seu tatame?",
        "contact_p": (
            "Conta quantos tatames você tem e a gente monta um orçamento. "
            "A visita pra avaliar a academia é gratuita."
        ),
        "contact_email": "Mandar um email",
        "contact_whatsapp": "Chamar no WhatsApp",
        "wa_msg": "Oi! Quero um orçamento do NO FLAGRA pra minha academia.",
        "wa_bubble_title": "Fala com a gente",
        "wa_bubble_text": "Tire suas dúvidas ou peça um orçamento direto pelo WhatsApp.",
        "wa_open": "Abrir conversa no WhatsApp",
        "wa_close": "Fechar",
        "footer_contact": "contato",
        "signup_title": "Comece sua academia",
        "label_gym_name": "Nome da academia",
        "label_your_name": "Seu nome",
        "label_email": "Email",
        "label_password": "Senha",
        "btn_create_account": "Criar conta",
        "hint_have_account": "Já tem uma conta?",
        "login_title": "Entrar",
        "btn_login": "Entrar",
        "hint_new_here": "Novo por aqui?",
        "err_name_required": "Digite seu nome.",
        "err_email_invalid": "Digite um email válido.",
        "err_gym_required": "Digite o nome da sua academia.",
        "err_password_short": "A senha precisa ter pelo menos 8 caracteres.",
        "err_email_taken": "Já existe uma conta com esse email — faça login.",
        "err_wrong_login": "Email ou senha incorretos.",
    },
    "en": {
        "nav_login": "Log in",
        "nav_dashboard": "Dashboard",
        "nav_logout": "Log out",
        "nav_start_gym": "Start your gym",
        "hero_h1": "Never miss the moment.",
        "hero_p": (
            "Press a button mat-side. Get the last 10 minutes, cut from "
            "continuous recording and ready to watch — before you even walk "
            "off the mat."
        ),
        "eyebrow_how": "How it works",
        "step1_h": "Press",
        "step1_p": "One button by the mat. No camera operator, no phone to dig out mid-roll.",
        "step2_h": "Cut",
        "step2_p": "The camera's already been rolling — the button just cuts the last 10 minutes from it.",
        "step3_h": "Review",
        "step3_p": "The clip shows up in your gym's library, ready to watch from your phone in seconds.",
        "step4_h": "Share",
        "step4_p": "Send it to your training partner, your coach, or save it for the next belt review.",
        "eyebrow_why": "Why gyms use it",
        "benefit1_h": "Never miss a submission",
        "benefit1_p": "The camera never stops rolling, so the moment is already saved by the time anyone thinks to hit record.",
        "benefit2_h": "One button, no operator",
        "benefit2_p": "Anyone on the mat can save a clip mid-roll. Nobody's job is “hold the phone.”",
        "benefit3_h": "One login for everyone",
        "benefit3_p": "Every member of your gym gets access to the same clip library — no shared phone, no group chat dump.",
        "benefit4_h": "A running history",
        "benefit4_p": "Every saved clip lives in the cloud, searchable by day, ready whenever you want to look back.",
        "showcase_h": "See it in action",
        "showcase_p": (
            "This is the actual dashboard your gym gets: a live view of the "
            "mat, one big button, and every saved clip grouped by day — black "
            "and yellow, built to be readable from across the room."
        ),
        "mock_live": "live view",
        "cta_band_h": "Ready to put one on your mat?",
        "cta_band_p": "Setting up more than one location, or want to talk pricing first?",
        "cta_band_link": "Get in touch",
        "nav_pricing": "Pricing",
        "nav_get_quote": "Request a quote",
        "hero_note": "Installed for you, at your gym. No camera operator, no app to download.",
        "hero_cta_secondary": "See how it works",
        "eyebrow_kit": "What your gym gets",
        "kit_h": "Installed and running.",
        "kit_p": (
            "You don't build anything and you don't configure anything. We come "
            "to the gym, install it, test it with your team, and leave it running."
        ),
        "kit1_h": "Camera over the mat",
        "kit1_p": "A fixed camera on a mount, positioned to cover the whole mat.",
        "kit2_h": "Wireless button",
        "kit2_p": "A tough button at the edge of the mat. Press it and you're done.",
        "kit3_h": "Local recorder",
        "kit3_p": "A small computer that lives at your gym and records 24 hours a day.",
        "kit4_h": "Cloud dashboard",
        "kit4_p": "The clip library your team opens from their phones.",
        "eyebrow_pricing": "Pricing",
        "pricing_h": "One install. One monthly fee.",
        "pricing_install_label": "Installation",
        "pricing_install_value": "quoted per gym",
        "pricing_install_note": "one-time · payment plans available",
        "pricing_install_1": "Camera, mount and power supply",
        "pricing_install_2": "Wireless button at the mat",
        "pricing_install_3": "Local recorder, installed",
        "pricing_install_4": "Cabling and configuration",
        "pricing_install_5": "On-site visit, tuning and team training",
        "pricing_monthly_label": "Monthly",
        "pricing_monthly_value": "R$ 150",
        "pricing_monthly_unit": "per month, per camera",
        "pricing_monthly_1": "Cloud clip library",
        "pricing_monthly_2": "Unlimited logins for your team",
        "pricing_monthly_3": "Updates and support included",
        "pricing_monthly_4": "No lock-in — cancel any time",
        "pricing_note": (
            "The install price depends on how many mats you have and on your "
            "gym's cabling. The quoting visit is free."
        ),
        "how_h": "From the mat to your phone, in four steps.",
        "how_p": (
            "The camera is already recording, all the time. The button just "
            "marks the part worth keeping."
        ),
        "why_h": "Built for people who train, not people who film.",
        "mock_press": "Save last 10 min",
        "mock_press_sub": "tap the button at the mat",
        "mock_today": "Today",
        "eyebrow_faq": "Questions",
        "faq_h": "Common questions",
        "faq1_q": "Do I need fast internet?",
        "faq1_a": (
            "No. Recording happens on the recorder that sits inside your gym. "
            "The internet is only used to upload the clips someone saved — "
            "never the whole day's video."
        ),
        "faq2_q": "What if the internet goes down?",
        "faq2_a": (
            "The camera keeps recording and the button keeps working. When the "
            "connection comes back, saved clips upload on their own."
        ),
        "faq3_q": "Who can see my gym's clips?",
        "faq3_a": (
            "Only the people you invite. Each gym has its own library, separate "
            "from every other gym's, and you control who gets in and who doesn't."
        ),
        "faq4_q": "Does it work with more than one mat?",
        "faq4_a": (
            "Yes. Each mat gets its own camera and its own button, and every "
            "clip lands in the same gym library."
        ),
        "faq5_q": "Does someone have to operate it?",
        "faq5_a": (
            "No. There's no camera operator and no phone to hold. Anyone on the "
            "mat can hit the button mid-roll."
        ),
        "faq6_q": "Do I need to install an app?",
        "faq6_a": (
            "No. Your team signs in from their phone's browser with the gym's "
            "login. It works on any phone."
        ),
        "contact_h": "Let's put one on your mat.",
        "contact_p": (
            "Tell us how many mats you have and we'll put a quote together. "
            "The visit to assess your gym is free."
        ),
        "contact_email": "Send us an email",
        "contact_whatsapp": "Message us on WhatsApp",
        "wa_msg": "Hi! I'd like a quote for NO FLAGRA for my gym.",
        "wa_bubble_title": "Talk to us",
        "wa_bubble_text": "Ask a question or request a quote straight over WhatsApp.",
        "wa_open": "Open WhatsApp chat",
        "wa_close": "Close",
        "footer_contact": "contact",
        "signup_title": "Start your gym",
        "label_gym_name": "Gym name",
        "label_your_name": "Your name",
        "label_email": "Email",
        "label_password": "Password",
        "btn_create_account": "Create account",
        "hint_have_account": "Already have an account?",
        "login_title": "Log in",
        "btn_login": "Log in",
        "hint_new_here": "New here?",
        "err_name_required": "Enter your name.",
        "err_email_invalid": "Enter a valid email.",
        "err_gym_required": "Enter your gym's name.",
        "err_password_short": "Password must be at least 8 characters.",
        "err_email_taken": "An account with that email already exists — log in instead.",
        "err_wrong_login": "Wrong email or password.",
    },
}


def get_locale():
    lang = request.args.get("lang")
    if lang in LOCALES:
        return lang
    cookie_lang = request.cookies.get("lang")
    if cookie_lang in LOCALES:
        return cookie_lang
    return DEFAULT_LOCALE


def t(key):
    locale = get_locale()
    return TRANSLATIONS[locale].get(key) or TRANSLATIONS[DEFAULT_LOCALE].get(key, key)
