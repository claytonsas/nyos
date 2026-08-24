/* =========================================================
   NYOS — main.js
   Lenis + GSAP ScrollTrigger, curseur, scroll horizontal,
   slides pinnées, terminal, tilt, compteurs.
   ========================================================= */
(() => {
  'use strict';

  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const IS_TOUCH = window.matchMedia('(hover: none)').matches;
  const $  = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => Array.from(c.querySelectorAll(s));
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

  let lenis = null;

  /* ---------------------------------------------------
     1. PRELOADER
     --------------------------------------------------- */
  const preloader = () => {
    const pre  = $('#pre');
    const num  = $('#preNum');
    const fill = $('#preFill');
    const log  = $('#preLog');
    const curtain = $('#curtain');
    if (!pre) return Promise.resolve();

    const steps = [
      'initialisation',
      'chargement des modules',
      'établissement du canal',
      'vérification d’intégrité',
      'prêt'
    ];

    document.documentElement.style.overflow = 'hidden';

    return new Promise(resolve => {
      if (REDUCED) {
        pre.style.display = 'none';
        document.documentElement.style.overflow = '';
        resolve();
        return;
      }

      const state = { v: 0 };
      window.gsap.to(state, {
        v: 100,
        duration: 1.35,
        ease: 'power2.inOut',
        onUpdate() {
          const v = Math.round(state.v);
          num.textContent = String(v).padStart(2, '0');
          fill.style.transform = `scaleX(${state.v / 100})`;
          log.textContent = steps[clamp(Math.floor(state.v / 25), 0, steps.length - 1)];
        },
        onComplete() {
          const tl = window.gsap.timeline({
            onComplete() {
              pre.style.display = 'none';
              document.documentElement.style.overflow = '';
              resolve();
            }
          });
          tl.to('.pre__inner', { y: -26, opacity: 0, duration: .38, ease: 'power3.in' })
            .set(curtain, { transformOrigin: 'bottom' })
            .to(curtain, { scaleY: 1, duration: .45, ease: 'power4.inOut' }, '-=.12')
            .set(pre, { opacity: 0 })
            .set(curtain, { transformOrigin: 'top' })
            .to(curtain, { scaleY: 0, duration: .55, ease: 'power4.inOut' });
        }
      });
    });
  };

  /* ---------------------------------------------------
     2. SMOOTH SCROLL (Lenis) + ScrollTrigger
     --------------------------------------------------- */
  const smoothScroll = () => {
    const { gsap, ScrollTrigger } = window;
    gsap.registerPlugin(ScrollTrigger);

    if (REDUCED || typeof window.Lenis === 'undefined') return;

    lenis = new window.Lenis({
      lerp: 0.095,
      wheelMultiplier: 1,
      smoothWheel: true,
      syncTouch: false
    });

    lenis.on('scroll', ScrollTrigger.update);
    gsap.ticker.add(t => lenis.raf(t * 1000));
    gsap.ticker.lagSmoothing(0);

    // ancres internes
    $$('a[href^="#"]').forEach(a => {
      a.addEventListener('click', e => {
        const id = a.getAttribute('href');
        if (!id || id === '#') return;
        const target = document.querySelector(id);
        if (!target) return;
        e.preventDefault();
        document.body.classList.remove('menu-open');
        lenis.scrollTo(target, { offset: -60, duration: 1.35 });
      });
    });
  };

  /* ---------------------------------------------------
     3. CURSEUR PERSONNALISÉ
     --------------------------------------------------- */
  const cursor = () => {
    if (IS_TOUCH) return;
    const el   = $('#cursor');
    const dot  = $('.cursor__dot');
    const ring = $('.cursor__ring');
    const label = $('#curLabel');
    if (!el) return;

    const pos = { x: innerWidth / 2, y: innerHeight / 2 };
    const ringPos = { ...pos };
    let dotPos = { ...pos };

    addEventListener('mousemove', e => { pos.x = e.clientX; pos.y = e.clientY; }, { passive: true });

    const loop = () => {
      dotPos.x += (pos.x - dotPos.x) * .55;
      dotPos.y += (pos.y - dotPos.y) * .55;
      ringPos.x += (pos.x - ringPos.x) * .16;
      ringPos.y += (pos.y - ringPos.y) * .16;
      dot.style.transform  = `translate(${dotPos.x}px, ${dotPos.y}px) translate(-50%,-50%)`;
      ring.style.transform = `translate(${ringPos.x}px, ${ringPos.y}px) translate(-50%,-50%)`;
      requestAnimationFrame(loop);
    };
    loop();

    $$('a, button, [data-cursor], [data-tilt]').forEach(t => {
      const mode = t.dataset.cursor || (t.hasAttribute('data-tilt') ? 'hover' : 'link');
      t.addEventListener('mouseenter', () => {
        document.body.classList.toggle('cur-hover', mode === 'hover');
        document.body.classList.toggle('cur-link', mode === 'link');
        if (mode === 'hover') label.textContent = t.dataset.label || 'voir';
      });
      t.addEventListener('mouseleave', () => {
        document.body.classList.remove('cur-hover', 'cur-link');
      });
    });
  };

  /* ---------------------------------------------------
     4. NAVIGATION
     --------------------------------------------------- */
  const nav = () => {
    const bar = $('#nav');
    const burger = $('#burger');
    if (!bar) return;
    let last = 0;

    const onScroll = () => {
      const y = window.scrollY;
      bar.classList.toggle('is-solid', y > 40);
      if (!document.body.classList.contains('menu-open')) {
        bar.classList.toggle('is-hidden', y > last && y > 260);
      }
      last = y;
    };
    addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    if (burger) {
      burger.addEventListener('click', () => {
        const open = document.body.classList.toggle('menu-open');
        burger.setAttribute('aria-expanded', String(open));
        burger.setAttribute('aria-label', open ? 'Fermer le menu' : 'Ouvrir le menu');
        if (lenis) open ? lenis.stop() : lenis.start();
      });
    }
    $$('[data-close]').forEach(a => a.addEventListener('click', () => {
      document.body.classList.remove('menu-open');
      if (lenis) lenis.start();
    }));
    addEventListener('keydown', e => {
      if (e.key === 'Escape' && document.body.classList.contains('menu-open')) {
        document.body.classList.remove('menu-open');
        if (lenis) lenis.start();
      }
    });
  };

  /* ---------------------------------------------------
     5. SCRAMBLE (effet décodage)
     --------------------------------------------------- */
  const scramble = (el, done) => {
    const chars = '!<>-_\\/[]{}—=+*^?#________';
    const original = el.textContent;
    let frame = 0;
    const queue = [...original].map((c, i) => {
      const start = Math.round(i * 0.5) + Math.floor(Math.random() * 6);
      return { from: c, to: c, start, end: start + 6 + Math.floor(Math.random() * 8) };
    });

    const run = () => {
      let out = '', complete = 0;
      for (const q of queue) {
        if (frame >= q.end) { complete++; out += q.to; }
        else if (frame >= q.start) {
          out += `<span style="opacity:.45">${chars[Math.floor(Math.random() * chars.length)]}</span>`;
        } else out += q.from;
      }
      el.innerHTML = out;
      if (complete === queue.length) { el.textContent = original; done && done(); return; }
      frame++;
      requestAnimationFrame(run);
    };
    run();
  };

  /* ---------------------------------------------------
     6. SPLIT + REVEALS
     --------------------------------------------------- */
  const splitWords = el => {
    const words = el.textContent.trim().split(/\s+/);
    el.innerHTML = words.map(w => `<span class="w">${w}</span>`).join(' ');
    return $$('.w', el);
  };

  const reveals = () => {
    const { gsap, ScrollTrigger } = window;

    // éléments simples
    $$('[data-rv]').forEach(el => {
      gsap.set(el, { opacity: 0, y: 26 });
      ScrollTrigger.create({
        trigger: el,
        start: 'top 88%',
        once: true,
        onEnter: () => gsap.to(el, { opacity: 1, y: 0, duration: 1, ease: 'expo.out' })
      });
    });

    // titres de section : décodage
    $$('.eyebrow').forEach(el => {
      if (el.dataset.scrambled) return;
      ScrollTrigger.create({
        trigger: el, start: 'top 92%', once: true,
        onEnter: () => { el.dataset.scrambled = '1'; if (!REDUCED) scramble(el); }
      });
    });

    // manifeste : mot par mot au scroll
    $$('[data-split-words]').forEach(el => {
      const words = splitWords(el);
      gsap.to(words, {
        opacity: 1,
        stagger: .06,
        ease: 'none',
        scrollTrigger: { trigger: el, start: 'top 78%', end: 'bottom 55%', scrub: .6 }
      });
    });
  };

  /* ---------------------------------------------------
     7. HERO
     --------------------------------------------------- */
  const hero = () => {
    const { gsap } = window;
    const chars = $$('#heroTitle .ch');
    if (!chars.length) return;

    const tl = gsap.timeline({ defaults: { ease: 'expo.out' } });
    gsap.set(chars, { yPercent: 118, opacity: 0, rotate: 6 });
    tl.to(chars, { yPercent: 0, opacity: 1, rotate: 0, duration: 1.5, stagger: .085 })
      .from('.hero__sub', { opacity: 0, y: 30, duration: .9 }, '-=1.25')
      .from('.scroll-cue', { opacity: 0, duration: .8 }, '-=.7');

    // parallaxe légère au scroll
    if (!REDUCED) {
      gsap.to('#heroTitle', {
        yPercent: -22, opacity: .18, ease: 'none',
        scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: .5 }
      });
      gsap.to('.hero__glow', {
        yPercent: 30, scale: 1.2, ease: 'none',
        scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: .8 }
      });
    }
  };

  /* ---------------------------------------------------
     8. MARQUEE (vitesse liée au scroll)
     --------------------------------------------------- */
  const marquee = () => {
    const track = $('#marqueeTrack');
    if (!track || REDUCED) return;
    const { gsap, ScrollTrigger } = window;

    const half = () => track.scrollWidth / 2;
    let x = 0, dir = 1, base = .55;

    ScrollTrigger.create({
      trigger: '#marquee',
      onUpdate: self => { dir = self.direction; }
    });

    gsap.ticker.add(() => {
      const vel = ScrollTrigger.isRefreshing ? 0 : Math.min(Math.abs(window.__scrollVel || 0), 40);
      x -= (base + vel * .05) * (dir >= 0 ? 1 : -1);
      const w = half();
      if (x <= -w) x += w;
      if (x > 0) x -= w;
      track.style.transform = `translate3d(${x}px,0,0)`;
    });

    // capture de la vélocité de scroll
    let lastY = window.scrollY, lastT = performance.now();
    addEventListener('scroll', () => {
      const now = performance.now();
      const dt = Math.max(now - lastT, 1);
      window.__scrollVel = (window.scrollY - lastY) / dt * 16;
      lastY = window.scrollY; lastT = now;
    }, { passive: true });
  };

  /* ---------------------------------------------------
     9. SCROLL HORIZONTAL — SERVICES
     --------------------------------------------------- */
  const horizontal = () => {
    const section = $('#services');
    const track = $('#hTrack');
    const idxEl = $('#panelIdx');
    if (!section || !track || REDUCED) return;
    const { gsap, ScrollTrigger } = window;

    const panels = $$('.panel', track);
    const distance = () => Math.max(0, track.scrollWidth - window.innerWidth + 48);

    gsap.to(track, {
      x: () => -distance(),
      ease: 'none',
      scrollTrigger: {
        trigger: section,
        start: 'top top',
        end: () => '+=' + (distance() + window.innerHeight * .4),
        pin: true,
        scrub: 1,
        invalidateOnRefresh: true,
        anticipatePin: 1,
        onUpdate: self => {
          const i = clamp(Math.round(self.progress * (panels.length - 1)), 0, panels.length - 1);
          if (idxEl) idxEl.textContent = String(i + 1).padStart(2, '0');
        }
      }
    });

    // léger décalage d'entrée
    panels.forEach((p, i) => {
      gsap.from(p, {
        opacity: 0, y: 40, duration: .9, ease: 'expo.out', delay: i * .05,
        scrollTrigger: { trigger: section, start: 'top 60%', once: true }
      });
    });
  };

  /* ---------------------------------------------------
     10. SLIDES PINNÉES — MÉTHODE
     --------------------------------------------------- */
  const pinnedSlides = () => {
    const section = $('#methode');
    const sticky  = $('#methodSticky');
    if (!section || !sticky || REDUCED) return;
    const { gsap, ScrollTrigger } = window;

    const slides = $$('.slide', sticky);
    const steps  = $$('#methodProg li');
    let current = 0;

    const show = i => {
      if (i === current) return;
      const prev = slides[current];
      const next = slides[i];
      const dir = i > current ? 1 : -1;
      current = i;

      gsap.killTweensOf([prev, next]);
      gsap.to(prev, { opacity: 0, duration: .35, ease: 'power2.out',
        onComplete: () => prev.classList.remove('on') });
      gsap.fromTo(next,
        { opacity: 0, y: 44 * dir },
        { opacity: 1, y: 0, duration: .75, ease: 'expo.out',
          onStart: () => next.classList.add('on') });
      gsap.fromTo(next.querySelectorAll('.slide__list li'),
        { opacity: 0, x: 18 },
        { opacity: 1, x: 0, duration: .6, stagger: .06, ease: 'expo.out', delay: .1 });

      steps.forEach((s, k) => s.classList.toggle('on', k === i));
    };

    ScrollTrigger.create({
      trigger: section,
      start: 'top top',
      end: () => '+=' + (slides.length * window.innerHeight),
      pin: sticky,
      scrub: false,
      anticipatePin: 1,
      invalidateOnRefresh: true,
      onUpdate: self => {
        const i = clamp(Math.floor(self.progress * slides.length), 0, slides.length - 1);
        show(i);
      }
    });
  };

  /* ---------------------------------------------------
     11. TERMINAL
     --------------------------------------------------- */
  const terminal = () => {
    const body = $('#termBody');
    if (!body) return;

    const L = (cls, txt) => ({ cls, txt });
    const scripts = {
      recon: [
        L('p', 'nyos@ops:~$ '), L('c', 'scope --load mission-demo.yaml'),
        L('o', '\n  périmètre chargé · 3 domaines · 1 plage IP · mandat signé le 12/03'),
        L('ok', '\n  [ok] hors-périmètre déclaré : 2 sous-domaines exclus\n\n'),
        L('p', 'nyos@ops:~$ '), L('c', 'recon --assets --passive'),
        L('o', '\n  énumération des sous-domaines .............. 47 trouvés'),
        L('o', '\n  résolution DNS ............................. 39 actifs'),
        L('o', '\n  empreinte technologique .................... 12 stacks'),
        L('w', '\n  [!] recette-v2.client.tld ................... exposée publiquement'),
        L('w', '\n  [!] legacy-api.client.tld .................. TLS 1.0 accepté'),
        L('ok', '\n\n  [ok] surface cartographiée · 39 cibles priorisées\n')
      ],
      exploit: [
        L('p', 'nyos@ops:~$ '), L('c', 'analyse --target app.client.tld --manuel'),
        L('o', '\n  contrôle d’accès horizontal ................ en cours'),
        L('e', '\n  [critique] référence directe non contrôlée sur /api/v1/invoices/{id}'),
        L('o', '\n      → un compte standard lit les factures d’autres clients'),
        L('o', '\n      → validé manuellement · preuve capturée · aucune donnée conservée'),
        L('o', '\n\n  gestion de session ......................... en cours'),
        L('w', '\n  [élevée]  jeton non invalidé après déconnexion'),
        L('o', '\n\n  téléversement de fichiers .................. en cours'),
        L('ok', '\n  [ok]      contrôle de type et d’extension conforme'),
        L('o', '\n\n  client notifié de la faille critique à 14h07 (délai : 41 min)\n')
      ],
      report: [
        L('p', 'nyos@ops:~$ '), L('c', 'rapport --build --format pdf'),
        L('o', '\n  compilation des constats ................... 23 entrées'),
        L('o', '\n  notation CVSS 4.0 .......................... appliquée'),
        L('o', '\n  croisement impact métier ................... appliqué'),
        L('o', '\n\n  ┌ critique ....... 1'),
        L('o', '\n  ├ élevée ......... 4'),
        L('o', '\n  ├ moyenne ........ 11'),
        L('o', '\n  └ faible ......... 7'),
        L('o', '\n\n  rapport exécutif ........................... 5 pages'),
        L('o', '\n  rapport technique .......................... 61 pages'),
        L('o', '\n  plan de remédiation priorisé ............... 23 actions'),
        L('ok', '\n\n  [ok] livrables générés · contre-audit planifié à J+30\n')
      ]
    };

    let raf = null, started = false, activeTab = 'recon';

    const type = key => {
      cancelAnimationFrame(raf);
      body.innerHTML = '';
      const seq = scripts[key];
      let li = 0, ci = 0, buf = '';
      const caret = '<span class="term__caret"></span>';

      const step = () => {
        if (li >= seq.length) { body.innerHTML = buf + caret; return; }
        const item = seq[li];
        const speed = item.cls === 'c' ? 3 : 4;
        ci += speed;
        const slice = item.txt.slice(0, ci)
          .replace(/&/g, '&amp;').replace(/</g, '&lt;');
        body.innerHTML = buf + `<span class="${item.cls}">${slice}</span>` + caret;
        if (ci >= item.txt.length) {
          buf += `<span class="${item.cls}">${item.txt.replace(/&/g, '&amp;').replace(/</g, '&lt;')}</span>`;
          li++; ci = 0;
        }
        raf = requestAnimationFrame(step);
      };
      step();
    };

    $$('.term__tab').forEach(btn => {
      btn.addEventListener('click', () => {
        $$('.term__tab').forEach(b => {
          b.classList.remove('on');
          b.setAttribute('aria-selected', 'false');
        });
        btn.classList.add('on');
        btn.setAttribute('aria-selected', 'true');
        activeTab = btn.dataset.tab;
        type(activeTab);
      });
    });

    if (REDUCED) {
      body.innerHTML = scripts.recon.map(i => `<span class="${i.cls}">${i.txt}</span>`).join('');
      return;
    }

    window.ScrollTrigger.create({
      trigger: '#terminal', start: 'top 65%', once: true,
      onEnter: () => { if (!started) { started = true; type(activeTab); } }
    });
  };

  /* ---------------------------------------------------
     12. TILT + LUEUR SUIVANT LA SOURIS
     --------------------------------------------------- */
  const tilt = () => {
    if (IS_TOUCH || REDUCED) return;
    const { gsap } = window;

    $$('[data-tilt]').forEach(el => {
      const strength = el.classList.contains('panel') ? 5 : 7;
      el.addEventListener('mousemove', e => {
        const r = el.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width;
        const py = (e.clientY - r.top) / r.height;
        el.style.setProperty('--mx', `${px * 100}%`);
        el.style.setProperty('--my', `${py * 100}%`);
        gsap.to(el, {
          rotateY: (px - .5) * strength,
          rotateX: -(py - .5) * strength,
          transformPerspective: 900,
          duration: .6, ease: 'power2.out'
        });
      });
      el.addEventListener('mouseleave', () => {
        gsap.to(el, { rotateX: 0, rotateY: 0, duration: .8, ease: 'elastic.out(1,.6)' });
      });
    });

    // boutons magnétiques
    $$('.btn').forEach(b => {
      b.addEventListener('mousemove', e => {
        const r = b.getBoundingClientRect();
        gsap.to(b, {
          x: (e.clientX - r.left - r.width / 2) * .28,
          y: (e.clientY - r.top - r.height / 2) * .38,
          duration: .5, ease: 'power3.out'
        });
      });
      b.addEventListener('mouseleave', () => {
        gsap.to(b, { x: 0, y: 0, duration: .7, ease: 'elastic.out(1,.5)' });
      });
    });
  };

  /* ---------------------------------------------------
     13. COMPTEURS
     --------------------------------------------------- */
  const counters = () => {
    const { gsap, ScrollTrigger } = window;
    $$('[data-count]').forEach(el => {
      const target = parseFloat(el.dataset.count);
      const suffix = el.dataset.suffix || '';
      const obj = { v: 0 };
      ScrollTrigger.create({
        trigger: el, start: 'top 88%', once: true,
        onEnter: () => gsap.to(obj, {
          v: target, duration: 1.8, ease: 'expo.out',
          onUpdate: () => {
            const sup = el.querySelector('sup');
            el.textContent = Math.round(obj.v) + suffix;
            if (sup) el.appendChild(sup);
          }
        })
      });
    });
  };

  /* ---------------------------------------------------
     14. FAQ (accordéon)
     --------------------------------------------------- */
  const accordion = () => {
    $$('.acc__item').forEach(item => {
      const btn = $('.acc__btn', item);
      const panel = $('.acc__panel', item);
      if (!btn || !panel) return;
      btn.setAttribute('aria-expanded', 'false');
      btn.addEventListener('click', () => {
        const open = item.classList.contains('on');
        // ferme les autres
        $$('.acc__item.on').forEach(o => {
          if (o === item) return;
          o.classList.remove('on');
          $('.acc__panel', o).style.height = '0px';
          $('.acc__btn', o).setAttribute('aria-expanded', 'false');
        });
        item.classList.toggle('on', !open);
        btn.setAttribute('aria-expanded', String(!open));
        panel.style.height = open ? '0px' : panel.scrollHeight + 'px';
        if (window.ScrollTrigger) setTimeout(() => window.ScrollTrigger.refresh(), 600);
      });
    });
  };

  /* ---------------------------------------------------
     15. HORLOGE + ANNÉE
     --------------------------------------------------- */
  const clock = () => {
    const targets = [$('#menuClock'), $('#footClock')].filter(Boolean);
    const y = $('#year');
    if (y) y.textContent = new Date().getFullYear();
    if (!targets.length) return;
    const tick = () => {
      const t = new Date().toLocaleTimeString('fr-FR', { hour12: false });
      targets.forEach(el => el.textContent = t);
    };
    tick();
    setInterval(tick, 1000);
  };

  /* ---------------------------------------------------
     16. FORMULAIRE (retour visuel)
     --------------------------------------------------- */
  const forms = () => {
    const form = $('#contactForm');
    if (!form) return;
    form.addEventListener('submit', e => {
      e.preventDefault();
      const btn = $('button[type="submit"]', form);
      const data = new FormData(form);
      const subject = encodeURIComponent(`[NYOS] Demande — ${data.get('societe') || 'sans société'}`);
      const bodyTxt = encodeURIComponent(
        `Nom : ${data.get('nom')}\n` +
        `Société : ${data.get('societe')}\n` +
        `Email : ${data.get('email')}\n` +
        `Type de mission : ${data.get('type')}\n` +
        `Périmètre : ${data.get('perimetre')}\n\n` +
        `${data.get('message')}\n`
      );
      if (btn) { btn.textContent = 'Ouverture de votre messagerie…'; }
      window.location.href = `mailto:contact@nyos.dev?subject=${subject}&body=${bodyTxt}`;
      setTimeout(() => { if (btn) btn.textContent = 'Envoyer la demande'; }, 3000);
    });
  };

  /* ---------------------------------------------------
     BOOT
     --------------------------------------------------- */
  const boot = async () => {
    if (!window.gsap) { document.querySelectorAll('[data-rv]').forEach(e => e.style.opacity = 1); return; }

    smoothScroll();
    cursor();
    nav();
    clock();
    accordion();
    forms();

    await preloader();

    hero();
    reveals();
    marquee();
    horizontal();
    pinnedSlides();
    terminal();
    tilt();
    counters();

    window.ScrollTrigger && window.ScrollTrigger.refresh();
    addEventListener('load', () => window.ScrollTrigger && window.ScrollTrigger.refresh());
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else boot();
})();
