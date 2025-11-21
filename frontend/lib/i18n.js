import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const LANG_KEY = "ui_language";
const DEFAULT_LANG = "ru";

const dictionaries = {
  en: {
    nav: {
      sanctum: "Sanctum",
      worlds: "Worlds",
      quest: "Quest",
      legends: "Legends",
      character: "Character",
      class: "Class",
    },
    layout: {
      badge: "RPG Academy",
      tagline: "Build your legend",
      login: "Login",
      register: "Join Legion",
      seasonLabel: "Season",
      seasonName: "Obsidian Dawn",
      toggleLabel: "Language",
      footerNote: "Made for the Diploma questline",
    },
    hero: {
      cardTitle: "Command Console",
      cardSubtitle: "You stand before the Academy sanctum",
      oath: "Current Oath",
      headlineTemplate: "Forge a legendary {{class}} destined for production.",
      fallbackClass: "Initiate",
      primaryCta: "Continue Adventure",
      secondaryCta: "Switch Class",
      badge: "You stand before the Academy sanctum",
    },
    sheet: {
      title: "Character Sheet",
      spec: "Spec",
      level: "Level",
      nextUnlock: "Next Unlock",
      nextUnlockValue: "Mission Map",
      xpLabel: "XP Trail",
      totalXp: "Total XP",
    },
    customizer: {
      title: "Avatar Customization",
      subtitle: "Tune armor, accents, and weapon glow to match your class.",
      archetype: "Archetype",
      palette: "Palette",
      slots: {
        hair: "Hair",
        armor: "Armor",
        accent: "Accent",
        weapon: "Weapon",
      },
      reset: "Reset to default",
    },
    quests: {
      title: "Quest Board",
      subtitle: "Pick your next objective",
      items: [
        {
          title: "Light the Forge",
          desc: "Spin up local docker stack and run first migrations.",
          reward: "+50 XP",
        },
        {
          title: "Scout the Worlds",
          desc: "Visit the world map and preview node coordinates.",
          reward: "+30 XP",
        },
        {
          title: "Master Your Class",
          desc: "Choose specialization and unlock class-specific quests.",
          reward: "Passive buff",
        },
      ],
    },
    codex: {
      title: "Codex Updates",
      subtitle: "Lore entries unlocked by progress",
      entries: [
        { title: "Backend Trials", detail: "Celery + Redis jobs proven in smoke tests." },
        { title: "Frontend Rituals", detail: "RPG UI system + onboarding revamp shipped." },
        { title: "Guild Reputation", detail: "CI/CD with coverage + Codecov tracking." },
      ],
    },
    relics: {
      items: [
        { label: "Artifact", value: "CI Sigil", icon: "sparkles" },
        { label: "Allies", value: "Celery sprites", icon: "flame" },
        { label: "Weather", value: "Stable build", icon: "compass" },
      ],
      statusLabel: "Status nominal",
      battlePlan: {
        title: "Battle Plan",
        subtitle: "Implementation checklist",
        items: ["Deploy redesigned UI kit", "Keep missions synced with backend", "Document 50% milestone"],
      },
      signals: {
        title: "Signals",
        subtitle: "Live telemetry",
        items: [
          {
            icon: "sparkles",
            text: "XP gain boosted for newcomers",
          },
          {
            icon: "swords",
            text: "Mission Gate locked until Intro complete",
          },
        ],
      },
    },
    map: {
      title: "Adventure Map",
      subtitle: "Track routes inspired by CodeCombat realms",
      routes: [
        { name: "Forge Path", detail: "Tutorial islands" },
        { name: "Crystal Archives", detail: "Data puzzles" },
        { name: "Shadow Wilds", detail: "Stealth missions" },
        { name: "Aurora Peaks", detail: "Boss gauntlet" },
      ],
      missions: [
        { id: "forge", name: "Obsidian Forge", tier: "Tier I", progress: 80, x: 18, y: 58 },
        { id: "plaza", name: "Sanctum Plaza", tier: "Tier II", progress: 45, x: 35, y: 32 },
        { id: "archives", name: "Crystal Archives", tier: "Tier III", progress: 25, x: 52, y: 60 },
        { id: "wilds", name: "Shadow Wilds", tier: "Tier IV", progress: 10, x: 70, y: 35 },
        { id: "spire", name: "Aurora Spire", tier: "Tier V", progress: 5, x: 84, y: 62 },
        { id: "citadel", name: "Prime Citadel", tier: "Final", progress: 0, x: 60, y: 18 },
      ],
    },
    auth: {
      login: {
        title: "Gate Access",
        subtitle: "Authenticate to continue",
        identifierLabel: "Identifier",
        identifierPlaceholder: "Email or username",
        passwordLabel: "Password",
        passwordPlaceholder: "••••••••",
        helper: "Tokens stored client-side; use /auth endpoints on backend for production flows.",
        submit: "Sign in",
        submitting: "Signing in…",
        success: "Signed in",
        error: "Login failed",
      },
      register: {
        title: "Join the Guild",
        subtitle: "Provision new hero",
        usernameLabel: "Username",
        usernamePlaceholder: "adventurer",
        emailLabel: "Email (optional)",
        emailPlaceholder: "you@example.com",
        passwordLabel: "Password",
        passwordPlaceholder: "••••••••",
        helper: "Registration hits /auth/register/ on the backend service; e-mail remains optional.",
        submit: "Create account",
        submitting: "Creating…",
        success: "Account created, please sign in",
        error: "Registration failed",
      },
    },
    classPage: {
      alignment: "Alignment",
      heading: "Choose your specialization",
      subheading: "Classes grant unique passives, cosmetic upgrades, and custom questlines.",
      cta: "Pledge allegiance",
      toastSuccess: "Class selected",
      classes: {
        django: {
          name: "Django Arcanist",
          desc: "ORM rituals, DRF glyphs, Celery familiars, Postgres temples.",
          focus: "Backend control",
          crest: "🛡️",
        },
        python: {
          name: "Python Spellblade",
          desc: "Scripts, algorithms, and automation scrolls for any guild quest.",
          focus: "Core mastery",
          crest: "🐍",
        },
        devops: {
          name: "DevOps Ranger",
          desc: "Docker rituals, CI/CD wards, and multi-cloud scouting expertise.",
          focus: "Deployment",
          crest: "⚙️",
        },
      },
    },
    profile: {
      title: "Character Sheet",
      account: "Account",
      accountHelper: "Use DRF auth endpoints to update credentials and tokens.",
      classLabel: "Class",
      attributesLabel: "Attribute",
      attributes: {
        wisdom: "Wisdom",
        dex: "Dexterity",
        focus: "Focus",
      },
      errors: {
        load: "Failed to load profile",
      },
      talents: {
        title: "Talents",
        subtitle: "Unlocked bonuses",
        items: [
          "XP gain +10% when missions chained",
          "Celery monitoring available from dashboard",
          "CI smoke tests visible in Codex",
        ],
      },
      inventory: {
        title: "Inventory",
        subtitle: "Key artifacts",
        items: [
          "✨ JWT Token — valid",
          "📜 Postman collection synced",
          "🗝️ GitLab deploy key stored in vault",
        ],
      },
    },
    leaderboard: {
      eyebrow: "Hall of legends",
      title: "Leaderboard",
      subtitle: "Completion streak boosts ranking every midnight reset.",
      columns: {
        rank: "Rank",
        player: "Player",
        level: "Level",
        xp: "XP",
        streak: "Streak",
      },
      loading: "Loading leaderboard…",
      empty: "No entries for these filters yet.",
      errors: {
        load: "Cannot load leaderboard",
      },
      successRefreshed: "Leaderboard updated",
      filters: {
        title: "Filters",
        subtitle: "Scope, track, and timeframe",
        scope: "Scope",
        period: "Period",
        track: "Track",
        scopeOptions: {
          global: "Global",
          track: "Track",
        },
        periodOptions: {
          all_time: "All time",
          weekly: "Weekly",
          monthly: "Monthly",
        },
        trackAny: "Any track",
        refresh: "Refresh",
        refreshing: "Refreshing…",
      },
    },
    missions: {
      dossier: "Quest dossier",
      rewardTitle: "Reward",
      rewardSubtitle: "XP payout",
      rewardHint: "Bonus scales with streaks. Complete prerequisites for full credit.",
      prerequisites: "Prerequisites",
      prerequisitesHint: "All previous intro quests must be cleared before unlocking this node.",
      strategy: "Strategy",
      strategySubtitle: "Suggested flow",
      strategyItems: [
        "Review docs or class materials",
        "Run backend tests locally",
        "Commit progress to unlock Gate",
      ],
      chapterLabel: "Chapter",
      state: "State",
      stateSubtitle: "Mission status",
      started: "Started",
      completed: "Completed",
      actions: "Actions",
      actionsSubtitle: "Trigger quest events",
      start: "Start",
      complete: "Complete",
      back: "Back",
      logTitle: "Mission log",
      logSubtitle: "Telemetry",
      logItems: [
        "🔁 API-backed start/complete endpoints mocked locally",
        "🎯 XP applied to player profile instantly",
        "🧪 Retry: handles DRF validation errors gracefully",
      ],
      status: {
        locked: "locked",
        available: "available",
        completed: "completed",
      },
      errors: {
        load: "Failed to load mission",
        start: "Cannot start mission",
        complete: "Cannot complete mission",
      },
      success: {
        started: "Mission started",
        completed: "Mission completed",
      },
      descr: "Mission intel loading",
      none: "None",
      xpGain: "+{xp} XP gained",
      noXp: "No XP this time",
      recap: "Mission #",
      runner: {
        title: "Lesson flow",
        subtitle: "Story → Quiz → Code pipeline",
        emptyTitle: "Task briefing",
        emptyBody: "No tasks available yet — ping content team.",
        noBody: "Content not provided yet.",
        storyCta: "Mark as studied",
        storyDone: "Story logged",
        saveError: "Could not save progress",
        quizCorrect: "Correct answer!",
        quizWrong: "Try again",
        storyComplete: "Marked as completed",
        codeDone: "Code validated",
        codeRetry: "Tests failed, adjust code",
        runnerError: "Runner is unavailable",
        status: "Status",
        attempts: "Attempts",
        score: "Score",
        updated: "Updated",
        stepper: {
          steps: {
            story: "Story",
            quiz: "Quiz",
            code: "Code",
            project: "Project",
            challenge: "Challenge",
          },
          mainStep: "Main step",
          sideQuest: "Side quest",
          minutes: "min",
        },
        quizFallback: [
          { label: "Option A", value: "a", isCorrect: true },
          { label: "Option B", value: "b", isCorrect: false },
        ],
        codePanel: {
          subtitle: "Code Runner",
          placeholder: "# Write your solution here",
          hint: "Runner executes {language} with sandboxed tests",
          run: "Run code",
          success: "All tests passed",
          fail: "Tests failed",
          tests: "Test suite",
        },
      },
      paywall: {
        badge: "Premium",
        message: "Premium-only objective. Unlock to continue.",
        cta: "Unlock premium",
        success: "Premium unlocked",
        error: "Checkout failed",
        title: "Unlock premium content",
        subtitle: "Side quests, XP boosts, and cohort perks",
        planCta: "Activate",
        processing: "Processing…",
  perksLabel: "Perks",
        plans: [
          { id: "novice", title: "Novice", price: "₽990", perks: ["3 missions", "Community chat"] },
          { id: "champion", title: "Champion", price: "₽1 990", perks: ["Full map", "Code review"] },
          { id: "founder", title: "Founder", price: "₽3 490", perks: ["1:1 session", "Named artifact"] },
        ],
      },
    },
    worldsPage: {
      premium: " · Premium",
      atlasTitle: "Atlas",
      atlasSubtitle: "Chart the archipelago of knowledge",
      atlasFallback: "Each world focuses on a different progression arc: fundamentals, backend mastery, DevOps rituals, and boss fights that mimic real interview scenarios.",
      autoRoute: "Auto-route to first mission",
      inspect: "Inspect Character",
      signalsTitle: "World Signals",
      signalsSubtitle: "Live scouting data",
      premiumSignal: "💎 Premium access required for final chapters",
      signals: [
        "⚔️ Intro Gate requires Class alignment",
        "🌊 Celery Reef stable – jobs succeed 99%",
        "🌋 Boss world unlocking at 75% completion",
      ],
      mapTitle: "World Map",
      nextMilestoneLabel: "Next milestone",
      progressLabel: "Progress",
      tiers: ["Novice Isles", "Adept Frontier", "Mythic Expanse", "Elder Rift"],
  defaultMilestone: "Intro quest",
      loading: "Loading scouting intel…",
      empty: "No worlds discovered for this track yet.",
    },
    common: {
      yes: "Yes",
      no: "Not yet",
      none: "None",
      identifier: "Identifier",
      errorBackend: "Check backend availability",
    },
  },
  ru: {
    nav: {
      sanctum: "Санктум",
      worlds: "Миры",
      quest: "Квест",
      legends: "Легенды",
      character: "Персонаж",
      class: "Класс",
    },
    layout: {
      badge: "Академия RPG",
      tagline: "Построй свою легенду",
      login: "Вход",
      register: "Присоединиться",
      seasonLabel: "Сезон",
      seasonName: "Обсидиановый Рассвет",
      toggleLabel: "Язык",
      footerNote: "Сделано для дипломного квеста",
    },
    hero: {
      cardTitle: "Командный консоль",
      cardSubtitle: "Перед тобой святилище Академии",
      oath: "Текущая клятва",
      headlineTemplate: "Куй легендарного {{class}}, готового к релизу.",
      fallbackClass: "Посвящённый",
      primaryCta: "Продолжить приключение",
      secondaryCta: "Сменить класс",
      badge: "Перед тобой святилище Академии",
    },
    sheet: {
      title: "Лист персонажа",
      spec: "Специализация",
      level: "Уровень",
      nextUnlock: "Следующее открытие",
      nextUnlockValue: "Карта миссий",
      xpLabel: "Полоса опыта",
      totalXp: "Всего XP",
    },
    customizer: {
      title: "Кастомизация героя",
      subtitle: "Настрой броню, подсветку и оружие под свой стиль.",
      archetype: "Архетип",
      palette: "Палитра",
      slots: {
        hair: "Волосы",
        armor: "Броня",
        accent: "Акцент",
        weapon: "Оружие",
      },
      reset: "Сбросить",
    },
    quests: {
      title: "Доска заданий",
      subtitle: "Выбери следующую цель",
      items: [
        {
          title: "Разжечь горн",
          desc: "Запусти Docker-стек локально и прогоняй миграции.",
          reward: "+50 XP",
        },
        {
          title: "Разведка миров",
          desc: "Загляни на карту и отметь координаты узлов.",
          reward: "+30 XP",
        },
        {
          title: "Освоить класс",
          desc: "Выбери специализацию и открой уникальные задания.",
          reward: "Пассивный бонус",
        },
      ],
    },
    codex: {
      title: "Хроники",
      subtitle: "Записи, которые ты открыл",
      entries: [
        { title: "Испытания бэкенда", detail: "Задания Celery + Redis прошли дымовые тесты." },
        { title: "Ритуалы фронтенда", detail: "Редизайн RPG интерфейса и онбординг готовы." },
        { title: "Репутация гильдии", detail: "CI/CD с покрытиями и отчётами Codecov." },
      ],
    },
    relics: {
      items: [
        { label: "Артефакт", value: "Печать CI", icon: "sparkles" },
        { label: "Соратники", value: "Духи Celery", icon: "flame" },
        { label: "Погода", value: "Стабильная сборка", icon: "compass" },
      ],
      statusLabel: "Состояние стабильно",
      battlePlan: {
        title: "Боевой план",
        subtitle: "Чеклист внедрения",
        items: ["Задеплоить UI-кит", "Синхронизировать миссии с backend", "Задокументировать прогресс 50%"],
      },
      signals: {
        title: "Сигналы",
        subtitle: "Живые телеметрии",
        items: [
          {
            icon: "sparkles",
            text: "Ускоренный рост XP для новичков",
          },
          {
            icon: "swords",
            text: "Врата миссий закрыты до завершения Интро",
          },
        ],
      },
    },
    map: {
      title: "Карта приключения",
      subtitle: "Отслеживай маршруты как в CodeCombat",
      routes: [
        { name: "Путь горна", detail: "Тренировочные острова" },
        { name: "Хрустальные архивы", detail: "Данные и головоломки" },
        { name: "Теневые чащи", detail: "Стелс-миссии" },
        { name: "Сияющие пики", detail: "Череда боссов" },
      ],
      missions: [
        { id: "forge", name: "Обсидиановый горн", tier: "I уровень", progress: 80, x: 18, y: 58 },
        { id: "plaza", name: "Площадь санктума", tier: "II уровень", progress: 45, x: 35, y: 32 },
        { id: "archives", name: "Хрустальные архивы", tier: "III уровень", progress: 25, x: 52, y: 60 },
        { id: "wilds", name: "Теневые чащи", tier: "IV уровень", progress: 10, x: 70, y: 35 },
        { id: "spire", name: "Сверкающий шпиль", tier: "V уровень", progress: 5, x: 84, y: 62 },
        { id: "citadel", name: "Главный цитадель", tier: "Финал", progress: 0, x: 60, y: 18 },
      ],
    },
    auth: {
      login: {
        title: "Вход в врата",
        subtitle: "Авторизуйтесь, чтобы продолжить",
        identifierLabel: "Логин или e-mail",
        identifierPlaceholder: "Почта или имя",
        passwordLabel: "Пароль",
        passwordPlaceholder: "••••••••",
        helper: "Токены хранятся на клиенте; в проде используйте backend /auth эндпоинты.",
        submit: "Войти",
        submitting: "Входим…",
        success: "Вы вошли",
        error: "Ошибка входа",
      },
      register: {
        title: "Присоединиться к гильдии",
        subtitle: "Создайте нового героя",
        usernameLabel: "Имя пользователя",
        usernamePlaceholder: "adventurer",
        emailLabel: "Email (необязательно)",
        emailPlaceholder: "you@example.com",
        passwordLabel: "Пароль",
        passwordPlaceholder: "••••••••",
        helper: "Регистрация использует /auth/register/ на backend; почта опциональна.",
        submit: "Создать аккаунт",
        submitting: "Создаём…",
        success: "Аккаунт создан, войдите",
        error: "Ошибка регистрации",
      },
    },
    classPage: {
      alignment: "Выравнивание",
      heading: "Выберите специализацию",
      subheading: "Классы дают пассивки, косметику и уникальные квесты.",
      cta: "Принять клятву",
      toastSuccess: "Класс выбран",
      classes: {
        django: {
          name: "Арканист Django",
          desc: "Ritual ORM, глифы DRF, фамильяры Celery, храмы Postgres.",
          focus: "Контроль backend",
          crest: "🛡️",
        },
        python: {
          name: "Пайтон-спеллблейд",
          desc: "Скрипты, алгоритмы и свитки автоматизации для любой гильдии.",
          focus: "Базовая магия",
          crest: "🐍",
        },
        devops: {
          name: "ДевОпс рейнджер",
          desc: "Docker-ритуалы, CI/CD печати и разведка мультиоблаков.",
          focus: "Деплой",
          crest: "⚙️",
        },
      },
    },
    profile: {
      title: "Лист персонажа",
      account: "Учётка",
      accountHelper: "Используйте DRF /auth чтобы менять данные и токены.",
      classLabel: "Класс",
      attributesLabel: "Характеристика",
      attributes: {
        wisdom: "Мудрость",
        dex: "Ловкость",
        focus: "Фокус",
      },
      errors: {
        load: "Не удалось загрузить профиль",
      },
      talents: {
        title: "Таланты",
        subtitle: "Открытые бонусы",
        items: [
          "Прирост XP +10% в цепочках миссий",
          "Мониторинг Celery доступен с дашборда",
          "CI дым-тесты отображаются в Кодексе",
        ],
      },
      inventory: {
        title: "Инвентарь",
        subtitle: "Ключевые артефакты",
        items: [
          "✨ JWT токен — активен",
          "📜 Коллекция Postman синхронизирована",
          "🗝️ GitLab deploy ключ хранится в хранилище",
        ],
      },
    },
    leaderboard: {
      eyebrow: "Зал легенд",
      title: "Таблица лидеров",
      subtitle: "Серия завершений повышает рейтинг в полночь.",
      columns: {
        rank: "Ранг",
        player: "Игрок",
        level: "Уровень",
        xp: "XP",
        streak: "Серия",
      },
      loading: "Загружаем таблицу…",
      empty: "Для выбранных фильтров пока нет данных.",
      errors: {
        load: "Не удалось загрузить лидерборд",
      },
      successRefreshed: "Таблица обновлена",
      filters: {
        title: "Фильтры",
        subtitle: "Выбери охват и период",
        scope: "Охват",
        period: "Период",
        track: "Трек",
        scopeOptions: {
          global: "Глобальный",
          track: "По треку",
        },
        periodOptions: {
          all_time: "За всё время",
          weekly: "Неделя",
          monthly: "Месяц",
        },
        trackAny: "Любой трек",
        refresh: "Обновить",
        refreshing: "Обновляем…",
      },
    },
    missions: {
      dossier: "Досье",
      rewardTitle: "Награда",
      rewardSubtitle: "Выдача XP",
      rewardHint: "Бонус растёт с сериями. Закройте пререквизиты для полного зачёта.",
      prerequisites: "Пререквизиты",
      prerequisitesHint: "Все вступительные миссии должны быть закрыты до открытия узла.",
      strategy: "Тактика",
      strategySubtitle: "Рекомендуемый план",
      strategyItems: [
        "Освежите документацию или материалы класса",
        "Прогоните backend-тесты локально",
        "Закоммитьте прогресс чтобы открыть Врата",
      ],
      chapterLabel: "Глава",
      state: "Состояние",
      stateSubtitle: "Статус миссии",
      started: "Старт",
      completed: "Завершена",
      actions: "Действия",
      actionsSubtitle: "Триггеры квеста",
      start: "Старт",
      complete: "Завершить",
      back: "Назад",
      logTitle: "Журнал",
      logSubtitle: "Телеметрия",
      logItems: [
        "🔁 API start/complete работают локально",
        "🎯 XP сразу улетает в профиль",
        "🧪 Повторы корректно обрабатывают ошибки DRF",
      ],
      status: {
        locked: "закрыто",
        available: "доступно",
        completed: "завершено",
      },
      errors: {
        load: "Не удалось загрузить миссию",
        start: "Нельзя стартовать миссию",
        complete: "Нельзя завершить миссию",
      },
      success: {
        started: "Миссия запущена",
        completed: "Миссия завершена",
      },
      descr: "Идёт загрузка досье",
      none: "Нет",
      xpGain: "+{xp} XP получено",
      noXp: "Без опыта на этот раз",
      recap: "Миссия #",
      runner: {
        title: "Шаги урока",
        subtitle: "Теория → Викторина → Код",
        emptyTitle: "Шаг миссии",
        emptyBody: "Задания скоро появятся",
        noBody: "Контент ещё не заполнен",
        storyCta: "Отметить как изучено",
        storyDone: "Теория отмечена",
        saveError: "Не удалось сохранить прогресс",
        quizCorrect: "Верно!",
        quizWrong: "Попробуй ещё раз",
        codeDone: "Код прошёл проверки",
        codeRetry: "Тесты упали — доработай",
        runnerError: "Раннер недоступен",
        status: "Статус",
        attempts: "Попытки",
        score: "Очки",
        updated: "Обновлено",
        stepper: {
          steps: {
            story: "Теория",
            quiz: "Викторина",
            code: "Код",
            project: "Проект",
            challenge: "Челлендж",
          },
          mainStep: "Основной шаг",
          sideQuest: "Сайд-квест",
          minutes: "мин",
        },
        quizFallback: [
          { label: "Черновой вариант A", value: "a", isCorrect: true },
          { label: "Черновой вариант B", value: "b", isCorrect: false },
        ],
        codePanel: {
          subtitle: "Код-раннер",
          placeholder: "# Напиши решение здесь",
          hint: "Раннер исполняет {language} и прогоняет мини-тесты",
          run: "Запустить код",
          success: "Все тесты зелёные",
          fail: "Тесты упали",
          tests: "Набор тестов",
        },
      },
      paywall: {
        badge: "Premium",
        message: "Премиум-квест. Разблокируй, чтобы продолжить.",
        cta: "Открыть премиум",
        success: "Доступ открыт",
        error: "Ошибка оплаты",
        title: "Открой премиум-контент",
        subtitle: "Сайд-квесты, бусты XP и групповые созвоны",
        planCta: "Активировать",
        processing: "Обработка…",
  perksLabel: "Бонусы",
        plans: [
          { id: "novice", title: "Novice", price: "₽990", perks: ["3 миссии", "Помощь в чате"] },
          { id: "champion", title: "Champion", price: "₽1 990", perks: ["Полная карта", "Код-ревью"] },
          { id: "founder", title: "Founder", price: "₽3 490", perks: ["1:1 с наставником", "Именной артефакт"] },
        ],
      },
    },
    worldsPage: {
      premium: " · Премиум",
      atlasTitle: "Атлас",
      atlasSubtitle: "Карта архипелага знаний",
      atlasFallback: "Каждый мир раскрывает арку прогресса: основы, backend-мастерство, DevOps-ритуалы и босс-файты под интервью.",
      autoRoute: "Автопереход к первой миссии",
      inspect: "Открыть персонажа",
      signalsTitle: "Сигналы мира",
      signalsSubtitle: "Живые сводки",
      premiumSignal: "💎 Премиум нужен для финальных глав",
      signals: [
        "⚔️ Врата Интро требуют выбранного класса",
        "🌊 Риф Celery стабилен — задачи успешны в 99%",
        "🌋 Босс-мир откроется на 75% прогресса",
      ],
      mapTitle: "Карта мира",
      nextMilestoneLabel: "Следующая цель",
      progressLabel: "Прогресс",
      tiers: ["Острова новичков", "Граница адептов", "Мифическое поле", "Разлом старейшин"],
  defaultMilestone: "Стартовая миссия",
      loading: "Загружаем разведданные…",
      empty: "Для трека пока нет миров.",
    },
    common: {
      yes: "Да",
      no: "Ещё нет",
      none: "Нет",
      identifier: "Идентификатор",
      errorBackend: "Проверьте доступность backend",
    },
  },
};

function getStoredLanguage() {
  if (typeof window === "undefined") return DEFAULT_LANG;
  return localStorage.getItem(LANG_KEY) || DEFAULT_LANG;
}

function persistLanguage(value) {
  if (typeof window === "undefined") return;
  localStorage.setItem(LANG_KEY, value);
}

function translate(dictionary, key) {
  return key
    .split(".")
    .reduce((acc, part) => (acc && acc[part] !== undefined ? acc[part] : undefined), dictionary);
}

const I18nContext = createContext({
  language: DEFAULT_LANG,
  dict: dictionaries[DEFAULT_LANG],
  t: (key) => translate(dictionaries[DEFAULT_LANG], key) || key,
  setLanguage: () => {},
  toggleLanguage: () => {},
  languages: ["ru", "en"],
});

export function I18nProvider({ children }) {
  const [language, setLanguage] = useState(DEFAULT_LANG);

  useEffect(() => {
    setLanguage(getStoredLanguage());
  }, []);

  const changeLanguage = useCallback((next) => {
    const safe = dictionaries[next] ? next : DEFAULT_LANG;
    persistLanguage(safe);
    setLanguage(safe);
  }, []);

  const toggleLanguage = useCallback(() => {
    setLanguage((prev) => {
      const next = prev === "ru" ? "en" : "ru";
      persistLanguage(next);
      return next;
    });
  }, []);

  const value = useMemo(() => {
    const dict = dictionaries[language] || dictionaries[DEFAULT_LANG];
    return {
      language,
      dict,
      t: (key) => translate(dict, key) || key,
      setLanguage: changeLanguage,
      toggleLanguage,
      languages: Object.keys(dictionaries),
    };
  }, [language, changeLanguage, toggleLanguage]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}

export function useDictionary() {
  const { dict } = useI18n();
  return dict;
}

export const languages = [
  { id: "ru", label: "RU" },
  { id: "en", label: "EN" },
];

export function formatHeadline(template, playerClass) {
  if (!template) return "";
  return template.replace("{{class}}", playerClass);
}

export { dictionaries };
