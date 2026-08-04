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
        "hero_note": (
            "Instalação completa na sua academia. Sem cameraman, sem app pra "
            "baixar. E dá pra testar 30 dias sem custo."
        ),
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
        "pricing_from": "a partir de",
        "pricing_monthly_value": "R$ 150",
        "pricing_monthly_unit": "por mês, por câmera *",
        "pricing_footnote": (
            "* Valor por câmera. O total depende de quantas câmeras sua "
            "academia usa — um tatame, uma câmera."
        ),
        "pricing_monthly_1": "Biblioteca de clipes na nuvem",
        "pricing_monthly_2": "Logins ilimitados pra sua equipe",
        "pricing_monthly_3": "Atualizações e suporte incluídos",
        "pricing_monthly_4": "Sem fidelidade — cancele quando quiser",
        "pricing_note": (
            "O valor da instalação depende de quantos tatames você tem e do "
            "cabeamento da sua academia. A visita pra orçamento é gratuita."
        ),
        "mission_h": "Não perca a finalização da sua vida.",
        "mission_p": (
            "Você treina três vezes por semana, cinco anos seguidos. O momento "
            "que você vai querer mostrar pro resto da vida dura oito segundos "
            "e acontece numa terça à noite, sem ninguém filmando."
        ),
        "mission_kicker": "O botão está na parede pra isso.",
        "eyebrow_offers": "Comece sem risco",
        "offers_h": "Teste antes de assinar.",
        "offers_p": (
            "Duas formas de começar sem tirar nada do bolso: um mês de teste "
            "com equipamento nosso, e um mês grátis pra cada academia que você "
            "indicar."
        ),
        "trial_label": "Teste de 30 dias",
        "trial_h": "A gente instala. Você usa 30 dias. Sem custo.",
        "trial_p": (
            "Temos um número limitado de equipamentos reservados pra teste. A "
            "gente instala na sua academia, sua equipe usa por 30 dias e no "
            "fim você decide. Não quis continuar? A gente busca — sem multa e "
            "sem mensalidade."
        ),
        "trial_fine": (
            "O equipamento é emprestado e continua sendo nosso durante o "
            "teste, então tem um contrato de comodato simples cobrindo perda "
            "ou dano. Só isso."
        ),
        "trial_cta": "Quero testar",
        "referral_label": "Indique uma academia",
        "referral_h": "Uma academia indicada, um mês grátis.",
        "referral_p": (
            "Indicou outra academia e ela fechou? A sua próxima mensalidade é "
            "por nossa conta. Sem limite: cinco academias, cinco meses."
        ),
        "referral_fine": (
            "O crédito entra quando a academia indicada conclui a instalação. "
            "Vale pra quem já é cliente e pra quem ainda está testando."
        ),
        "referral_cta": "Indicar uma academia",
        "wa_msg_trial": "Oi! Quero saber do teste de 30 dias do NO FLAGRA.",
        "wa_msg_referral": "Oi! Quero indicar uma academia pro NO FLAGRA.",
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
        "faq8_q": "O teste de 30 dias tem pegadinha?",
        "faq8_a": (
            "Não tem mensalidade, não tem taxa de instalação e não tem multa "
            "pra devolver. O que existe é um contrato de comodato: o "
            "equipamento é nosso durante o teste, e sua academia responde por "
            "perda ou dano. Se decidir continuar depois dos 30 dias, a gente "
            "aproveita o que já está instalado."
        ),
        "faq7_q": "Dá pra mudar o tempo do clipe?",
        "faq7_a": (
            "Dá. Dez minutos é o padrão, porque cobre um round inteiro com "
            "folga. Na instalação a gente ajusta pro que fizer sentido na sua "
            "academia — menos pra treino de queda, mais pra rolinho longo. "
            "Clipe mais longo só ocupa mais espaço e demora um pouco mais pra "
            "subir."
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
        "nav_about": "Sobre",
        "nav_privacy": "Privacidade",
        "nav_terms": "Termos",
        "meta_desc": (
            "Um botão do lado do tatame salva os últimos 10 minutos de "
            "treino. Câmera, botão e gravador instalados na sua academia, "
            "com biblioteca de clipes na nuvem. A partir de R$ 150/mês."
        ),
        "og_image_alt": "Tatame de jiu-jitsu visto pela câmera do NO FLAGRA",
        "eyebrow_showcase": "Veja funcionando",
        "showcase_badge": "gravando",
        "showcase_video_alt": (
            "Treino de jiu-jitsu no tatame, gravado pela câmera fixa do NO FLAGRA"
        ),
        "showcase_caption": (
            "Filmagem real de uma câmera NO FLAGRA instalada. É esse "
            "enquadramento que fica gravando o tempo todo — o botão só "
            "recorta os últimos minutos dele, 10 por padrão."
        ),
        "button_photo_alt": (
            "Botão vermelho do NO FLAGRA e a câmera instalados na parede da "
            "academia, na saída do tatame"
        ),
        "button_photo_h": "O botão fica na parede, não no seu bolso",
        "button_photo_p": (
            "Câmera no alto, botão na altura da mão, o resto escondido. Quem "
            "acabou de dar a finalização aperta na saída do tatame — sem "
            "celular no chão, sem pedir pra ninguém filmar."
        ),
        "legal_updated": "Atualizado em",
        "legal_back": "Voltar para a página inicial",
        "meta_desc_about": (
            "Quem faz o NO FLAGRA: por que um botão do lado do tatame resolve "
            "melhor o problema de gravar treino do que um cameraman."
        ),
        "about_title": "Sobre",
        "about_h1": "Feito por quem cansou de perder a finalização.",
        "about_lead": (
            "O NO FLAGRA nasceu de um problema chato e muito específico: a "
            "melhor coisa que acontece no treino quase nunca está sendo "
            "filmada."
        ),
        "about_s1_h": "O problema",
        "about_s1_p": (
            "Todo mundo que treina conhece a cena. Rolou uma passagem "
            "perfeita, uma raspagem que ninguém esperava, uma finalização "
            "que você tentou por seis meses — e ninguém filmou. Quando "
            "alguém lembra do celular, o momento já passou. Pedir pra "
            "alguém ficar de fora do treino segurando o telefone resolve "
            "gravando, mas tira uma pessoa do tatame."
        ),
        "about_s2_h": "A ideia",
        "about_s2_p": (
            "A gente inverteu a ordem. Em vez de começar a gravar quando "
            "algo acontece, a câmera grava o tatame o tempo todo, num "
            "gravador que fica dentro da academia. O botão não liga câmera "
            "nenhuma: ele recorta os últimos minutos do que já estava "
            "gravado — 10 por padrão, ajustável na instalação. O botão é uma "
            "tesoura, não uma câmera — por isso "
            "funciona mesmo se você lembrar de apertar só depois que acabou."
        ),
        "about_s3_h": "Como a gente trabalha",
        "about_s3_p": (
            "A gente vai até a academia, instala, posiciona a câmera pra "
            "pegar o tatame inteiro, testa com a sua equipe e deixa "
            "rodando. Você não monta nada e não configura nada. Se der "
            "problema, você fala com a gente no WhatsApp e quem responde é "
            "quem construiu o sistema — não tem central de atendimento no "
            "meio."
        ),
        "about_s4_h": "Onde estamos",
        "about_s4_p": (
            "O sistema roda hoje em academia de verdade, em uso diário, e "
            "está sendo aberto para novas unidades. O código do projeto é "
            "público no GitHub — dá pra ver exatamente como o vídeo é "
            "gravado, cortado e guardado, sem precisar acreditar na nossa "
            "palavra."
        ),
        "about_cta_h": "Quer ver no seu tatame?",
        "about_cta_p": (
            "A visita pra avaliar a academia e montar o orçamento é "
            "gratuita. Chama no WhatsApp e a gente marca."
        ),
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
        "hero_note": (
            "Installed for you, at your gym. No camera operator, no app to "
            "download. And you can try it free for 30 days."
        ),
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
        "pricing_from": "starting at",
        "pricing_monthly_value": "R$ 150",
        "pricing_monthly_unit": "per month, per camera *",
        "pricing_footnote": (
            "* Per camera. Your total depends on how many cameras your gym "
            "uses — one mat, one camera."
        ),
        "pricing_monthly_1": "Cloud clip library",
        "pricing_monthly_2": "Unlimited logins for your team",
        "pricing_monthly_3": "Updates and support included",
        "pricing_monthly_4": "No lock-in — cancel any time",
        "pricing_note": (
            "The install price depends on how many mats you have and on your "
            "gym's cabling. The quoting visit is free."
        ),
        "mission_h": "Don't miss the submission of your life.",
        "mission_p": (
            "You train three times a week, five years straight. The moment "
            "you'll want to show for the rest of your life lasts eight seconds "
            "and happens on a Tuesday night, with nobody filming."
        ),
        "mission_kicker": "That's what the button on the wall is for.",
        "eyebrow_offers": "Start without the risk",
        "offers_h": "Try it before you sign.",
        "offers_p": (
            "Two ways to start without spending anything: a month's trial on "
            "our equipment, and a free month for every gym you refer."
        ),
        "trial_label": "30-day tryout",
        "trial_h": "We install it. You use it for 30 days. No cost.",
        "trial_p": (
            "We keep a limited number of units set aside for trials. We "
            "install one at your gym, your team uses it for 30 days, and at "
            "the end you decide. Not for you? We come and collect it — no fee, "
            "no monthly bill."
        ),
        "trial_fine": (
            "The equipment is on loan and stays ours for the length of the "
            "trial, so there's a short loan agreement covering loss or damage. "
            "That's the whole of it."
        ),
        "trial_cta": "Ask about the tryout",
        "referral_label": "Refer a gym",
        "referral_h": "One gym referred, one month free.",
        "referral_p": (
            "Referred another gym and they signed? Your next month is on us. "
            "No cap: five gyms, five months."
        ),
        "referral_fine": (
            "The credit lands once the referred gym's install is finished. "
            "Open to current customers and to gyms still on trial."
        ),
        "referral_cta": "Refer a gym",
        "wa_msg_trial": "Hi! I'd like to know about the NO FLAGRA 30-day tryout.",
        "wa_msg_referral": "Hi! I'd like to refer a gym to NO FLAGRA.",
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
        "faq8_q": "Is there a catch to the 30-day tryout?",
        "faq8_a": (
            "No monthly bill, no install fee, and no penalty for giving it "
            "back. What there is: a loan agreement. The equipment is ours for "
            "the length of the trial, and your gym is on the hook for loss or "
            "damage. Decide to stay after the 30 days and we keep what's "
            "already installed."
        ),
        "faq7_q": "Can the clip length be changed?",
        "faq7_a": (
            "Yes. Ten minutes is the default, because it comfortably covers a "
            "full round. We set it at install to whatever suits your gym — "
            "shorter for takedown drilling, longer for extended rolls. A "
            "longer clip simply takes more storage and a little longer to "
            "upload."
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
        "nav_about": "About",
        "nav_privacy": "Privacy",
        "nav_terms": "Terms",
        "meta_desc": (
            "A button beside the mat saves the last 10 minutes of training. "
            "Camera, button and recorder installed at your gym, with a cloud "
            "clip library. From R$150/month."
        ),
        "og_image_alt": "A jiu-jitsu mat seen through the NO FLAGRA camera",
        "eyebrow_showcase": "See it in action",
        "showcase_badge": "recording",
        "showcase_video_alt": (
            "Jiu-jitsu training on the mat, recorded by the fixed NO FLAGRA camera"
        ),
        "showcase_caption": (
            "Real footage from an installed NO FLAGRA camera. This is the "
            "frame that keeps rolling all the time — the button just cuts the "
            "last few minutes out of it, 10 by default."
        ),
        "button_photo_alt": (
            "The NO FLAGRA red button and camera mounted on the gym wall, "
            "on the way off the mat"
        ),
        "button_photo_h": "The button lives on the wall, not in your pocket",
        "button_photo_p": (
            "Camera up high, button at hand height, everything else out of "
            "sight. Whoever just landed the submission hits it on the way off "
            "the mat — no phone on the floor, no asking someone to film."
        ),
        "legal_updated": "Last updated",
        "legal_back": "Back to the home page",
        "meta_desc_about": (
            "The people behind NO FLAGRA, and why a button beside the mat "
            "beats having someone film your training."
        ),
        "about_title": "About",
        "about_h1": "Built by people tired of missing the finish.",
        "about_lead": (
            "NO FLAGRA came out of an annoying and very specific problem: the "
            "best thing that happens in training is almost never being "
            "filmed."
        ),
        "about_s1_h": "The problem",
        "about_s1_p": (
            "Anyone who trains knows the scene. A perfect pass, a sweep "
            "nobody saw coming, a submission you'd been chasing for six "
            "months — and no one was recording. By the time someone "
            "remembers their phone, the moment is gone. Asking someone to "
            "sit out and hold a phone does solve the filming, but it takes a "
            "person off the mat."
        ),
        "about_s2_h": "The idea",
        "about_s2_p": (
            "We flipped the order. Instead of starting to record when "
            "something happens, the camera records the mat continuously, on "
            "a recorder that lives inside the gym. The button doesn't start "
            "any camera: it cuts the last few minutes out of what was already "
            "recorded — 10 by default, adjustable at install. The button is a "
            "pair of scissors, not a camera — "
            "which is why it still works when you only remember to press it "
            "after the round ended."
        ),
        "about_s3_h": "How we work",
        "about_s3_p": (
            "We come to the gym, install it, position the camera to cover "
            "the whole mat, test it with your team and leave it running. You "
            "don't build anything and you don't configure anything. If "
            "something breaks you message us on WhatsApp, and the person who "
            "answers is the person who built the system — there's no call "
            "centre in between."
        ),
        "about_s4_h": "Where we are",
        "about_s4_p": (
            "The system runs today in a real gym, in daily use, and is being "
            "opened up to new locations. The project's code is public on "
            "GitHub — you can see exactly how video is recorded, cut and "
            "stored, without having to take our word for it."
        ),
        "about_cta_h": "Want one on your mat?",
        "about_cta_p": (
            "The visit to assess your gym and put a quote together is free. "
            "Message us on WhatsApp and we'll set it up."
        ),
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
