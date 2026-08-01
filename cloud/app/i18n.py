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
