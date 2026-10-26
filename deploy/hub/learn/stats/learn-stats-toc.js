(function () {
  const ROADMAP = [
  {
    "group": "I. 데이터와 기술통계",
    "items": [
      {
        "n": "01",
        "slug": "data-and-variables",
        "title": "데이터와 변수",
        "soon": false,
        "macro_relevance": 3
      },
      {
        "n": "02",
        "slug": "population-and-sampling",
        "title": "모집단과 표본, 자료 수집과 편향",
        "soon": false,
        "macro_relevance": 3
      },
      {
        "n": "03",
        "slug": "graphs",
        "title": "그래프로 보는 데이터와 분포",
        "soon": false,
        "macro_relevance": 3
      },
      {
        "n": "04",
        "slug": "mean-and-median",
        "title": "평균과 중앙값",
        "soon": false,
        "macro_relevance": 3
      },
      {
        "n": "05",
        "slug": "quantiles",
        "title": "분위수와 상자그림",
        "soon": false,
        "macro_relevance": 3
      },
      {
        "n": "06",
        "slug": "spread",
        "title": "분산과 표준편차",
        "soon": false,
        "macro_relevance": 2
      },
      {
        "n": "07",
        "slug": "iqr-outliers",
        "title": "이상치와 IQR",
        "soon": false,
        "macro_relevance": 3
      }
    ]
  },
  {
    "group": "II. 확률과 표본의 불확실성",
    "items": [
      {
        "n": "08",
        "slug": "probability",
        "title": "확률의 기초와 조건부확률",
        "soon": false,
        "macro_relevance": 2
      },
      {
        "n": "09",
        "slug": "probability-distributions",
        "title": "확률변수와 확률분포",
        "soon": false,
        "macro_relevance": 1
      },
      {
        "n": "10",
        "slug": "sampling-distributions",
        "title": "표본분포와 중심극한정리",
        "soon": false,
        "macro_relevance": 2
      },
      {
        "n": "11",
        "slug": "sample-size",
        "title": "표준오차와 표본수",
        "soon": false,
        "macro_relevance": 3
      }
    ]
  },
  {
    "group": "III. 추정과 검정",
    "items": [
      {
        "n": "12",
        "slug": "confidence-intervals",
        "title": "점추정과 신뢰구간",
        "soon": false,
        "macro_relevance": 2
      },
      {
        "n": "13",
        "slug": "hypothesis-tests",
        "title": "가설검정과 p값",
        "soon": false,
        "macro_relevance": 2
      },
      {
        "n": "14",
        "slug": "comparing-groups",
        "title": "두 집단 비교와 효과크기",
        "soon": false,
        "macro_relevance": 2
      },
      {
        "n": "15",
        "slug": "multiple-groups-and-categorical",
        "title": "여러 집단과 범주형 자료의 비교",
        "soon": false,
        "macro_relevance": 2
      }
    ]
  },
  {
    "group": "IV. 상관과 회귀",
    "items": [
      {
        "n": "16",
        "slug": "correlation",
        "title": "상관관계와 인과관계",
        "soon": false,
        "macro_relevance": 3
      },
      {
        "n": "17",
        "slug": "regression",
        "title": "단순선형회귀와 최소제곱법",
        "soon": false,
        "macro_relevance": 3
      },
      {
        "n": "18",
        "slug": "residuals",
        "title": "잔차와 회귀모형의 가정",
        "soon": false,
        "macro_relevance": 3
      },
      {
        "n": "19",
        "slug": "multiple-regression",
        "title": "다중회귀와 변수의 해석",
        "soon": false,
        "macro_relevance": 3
      },
      {
        "n": "20",
        "slug": "log-regression",
        "title": "로그변환과 비선형 관계",
        "soon": false,
        "macro_relevance": 3
      },
      {
        "n": "21",
        "slug": "model-fit",
        "title": "회귀모형의 적합도와 추정의 불확실성",
        "soon": false,
        "macro_relevance": 3
      }
    ]
  },
  {
    "group": "V. 예측과 모형 평가",
    "items": [
      {
        "n": "22",
        "slug": "supervised-unsupervised",
        "title": "통계적 설명과 예측, 지도학습과 비지도학습",
        "soon": false,
        "macro_relevance": 2
      },
      {
        "n": "23",
        "slug": "train-validation-test",
        "title": "학습·검증·시험 자료와 데이터 누수",
        "soon": false,
        "macro_relevance": 2
      },
      {
        "n": "24",
        "slug": "overfitting",
        "title": "과적합과 편향–분산의 균형",
        "soon": false,
        "macro_relevance": 2
      },
      {
        "n": "25",
        "slug": "prediction-errors",
        "title": "예측오차: MAE·RMSE·MAPE",
        "soon": false,
        "macro_relevance": 3
      },
      {
        "n": "26",
        "slug": "cross-validation",
        "title": "교차검증과 모형 선택",
        "soon": false,
        "macro_relevance": 3
      },
      {
        "n": "27",
        "slug": "regularization",
        "title": "규제: 릿지와 라쏘",
        "soon": false,
        "macro_relevance": 3
      }
    ]
  },
  {
    "group": "VI. 기초 머신러닝과 종합 해석",
    "items": [
      {
        "n": "28",
        "slug": "classification",
        "title": "분류와 로지스틱 회귀",
        "soon": false,
        "macro_relevance": 2
      },
      {
        "n": "29",
        "slug": "knn",
        "title": "최근접 이웃과 변수의 스케일",
        "soon": false,
        "macro_relevance": 3
      },
      {
        "n": "30",
        "slug": "decision-tree",
        "title": "의사결정나무",
        "soon": false,
        "macro_relevance": 2
      },
      {
        "n": "31",
        "slug": "clustering",
        "title": "군집분석",
        "soon": false,
        "macro_relevance": 2
      },
      {
        "n": "32",
        "slug": "reading-results",
        "title": "통계 결과를 읽고 판단하는 법",
        "soon": false,
        "macro_relevance": 3
      }
    ]
  }
];

  const BASE = "/learn/stats/";

  function slugify(text) {
    return (
      text
        .trim()
        .toLowerCase()
        .replace(/[^\w\u3131-\uD79D\s-]/g, "")
        .replace(/\s+/g, "-")
        .replace(/-+/g, "-")
        .slice(0, 48) || "section"
    );
  }

  function currentSlug() {
    const parts = window.location.pathname.replace(/\/+$/, "").split("/");
    const statsIdx = parts.indexOf("stats");
    if (statsIdx === -1) return null;
    const slug = parts[statsIdx + 1];
    return slug || null;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function itemLabel(item) {
    return item.n ? `${item.n}. ${item.title}` : item.title;
  }

  function appendItem(ul, item, activeSlug) {
    const li = document.createElement("li");
    li.dataset.macroRelevance = item.macro_relevance;
    if (item.soon) {
      const span = el("span", "is-soon", `${itemLabel(item)} · 작성 예정`);
      li.appendChild(span);
      ul.appendChild(li);
      return;
    }
    const a = document.createElement("a");
    a.href = `${BASE}${item.slug}/`;
    a.textContent = itemLabel(item);
    const levels = { 3: ["★★★", "핵심"], 2: ["★★☆", "권장"], 1: ["★☆☆", "심화"] };
    const [stars, label] = levels[item.macro_relevance];
    const badge = el("span", "learn-relevance");
    badge.setAttribute("aria-label", `Macro 활용도 ${item.macro_relevance}단계, ${label}`);
    const icon = el("span", "", stars);
    icon.setAttribute("aria-hidden", "true");
    badge.append(icon);
    a.append(document.createTextNode(" "), badge);
    if (activeSlug && item.slug === activeSlug) {
      a.classList.add("is-current-chapter");
      a.setAttribute("aria-current", "page");
    }
    li.appendChild(a);
    ul.appendChild(li);
  }

  function buildRoadmapList(container) {
    const title = el("p", "learn-toc__heading", "과정 목차");
    container.appendChild(title);
    const nav = el("nav", "learn-toc__chapters");
    nav.setAttribute("aria-label", "학습 로드맵");

    ROADMAP.forEach((group) => {
      const block = el("div", "learn-toc__group");
      block.appendChild(el("p", "learn-toc__group-title", group.group));
      const ul = el("ul", "learn-toc__list");
      group.items.forEach((item) => appendItem(ul, item));
      block.appendChild(ul);
      nav.appendChild(block);
    });
    container.appendChild(nav);
  }

  function buildChapterList(container, activeSlug) {
    const title = el("p", "learn-toc__heading", "전체 목차");
    container.appendChild(title);
    const nav = el("nav", "learn-toc__chapters");
    nav.setAttribute("aria-label", "전체 장");

    ROADMAP.forEach((group) => {
      const block = el("div", "learn-toc__group");
      block.appendChild(el("p", "learn-toc__group-title", group.group));
      const ul = el("ul", "learn-toc__list");
      group.items.forEach((item) => appendItem(ul, item, activeSlug));
      block.appendChild(ul);
      nav.appendChild(block);
    });
    container.appendChild(nav);
  }

  function ensureSectionIds(article) {
    const used = new Set([...document.querySelectorAll("[id]")].map((node) => node.id));
    article.querySelectorAll(".learn-chapter__step").forEach((step, index) => {
      if (step.id) {
        used.add(step.id);
        return;
      }
      const h2 = step.querySelector("h2");
      let id = slugify(h2 ? h2.textContent : `section-${index + 1}`);
      let n = 2;
      while (used.has(id)) {
        id = `${id}-${n++}`;
      }
      step.id = id;
      used.add(id);
    });

    const caution = article.querySelector(".learn-caution");
    if (caution && !caution.id) caution.id = "caution";

    const more = article.querySelector("details.learn-more");
    if (more && !more.id) more.id = "learn-more";

    const cta = article.querySelector(".learn-macro-cta");
    if (cta && !cta.id) cta.id = "macro-cta";
  }

  function buildSectionList(container, article) {
    const title = el("p", "learn-toc__heading learn-toc__heading--sections", "이 장");
    container.appendChild(title);
    const nav = el("nav", "learn-toc__sections");
    nav.setAttribute("aria-label", "이 장 목차");
    const ul = el("ul", "learn-toc__list learn-toc__list--sections");

    article.querySelectorAll(".learn-chapter__step").forEach((step) => {
      const label = step.querySelector(".learn-chapter__label");
      const h2 = step.querySelector("h2");
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `#${step.id}`;
      a.textContent = step.dataset.tocLabel || h2?.textContent || label?.textContent || "섹션";
      a.dataset.tocTarget = step.id;
      li.appendChild(a);
      ul.appendChild(li);
    });

    const extras = [
      { sel: ".learn-caution", label: "주의" },
      { sel: "details.learn-more", label: "조금 더 알아보기" },
      { sel: ".learn-macro-cta", label: "CH2 Macro" },
    ];
    extras.forEach(({ sel, label }) => {
      const node = article.querySelector(sel);
      if (!node || !node.id || node.closest(".learn-chapter__step")) return;
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `#${node.id}`;
      a.textContent = label;
      a.dataset.tocTarget = node.id;
      li.appendChild(a);
      ul.appendChild(li);
    });

    nav.appendChild(ul);
    container.appendChild(nav);
    return nav;
  }

  function setupScrollSpy(sectionNav) {
    const links = sectionNav.querySelectorAll("a[data-toc-target]");
    if (!links.length) return;

    const targets = [...links]
      .map((link) => document.getElementById(link.dataset.tocTarget))
      .filter(Boolean);

    const setActive = (id) => {
      links.forEach((link) => {
        link.classList.toggle("is-active", link.dataset.tocTarget === id);
      });
    };

    let pending = false;
    function update() {
      pending = false;
      const marker = Math.min(180, window.innerHeight * 0.25);
      let current = targets[0];
      let nearest = -Infinity;
      for (const target of targets) {
        const top = target.getBoundingClientRect().top;
        if (top <= marker && top > nearest) { current = target; nearest = top; }
      }
      if (current) setActive(current.id);
    }
    window.addEventListener("scroll", () => {
      if (!pending) { pending = true; requestAnimationFrame(update); }
    }, { passive: true });
    window.addEventListener("resize", update);
    update();
  }

  function setupReader(page, aside, tocDetails) {
    const toolbar = el("div", "learn-reader-bar");
    toolbar.setAttribute("aria-label", "읽기 설정");
    const home = el("a", "learn-reader-home", "통계 학습");
    home.href = BASE;
    toolbar.appendChild(home);
    const controls = el("div", "learn-reader-controls");
    if (page.querySelector(".learn-chapter")) {
      const tocButton = el("button", "learn-reader-toc-button", "목차");
      tocButton.type = "button";
      tocDetails.id = "learn-reader-toc";
      tocButton.setAttribute("aria-controls", tocDetails.id);
      tocButton.addEventListener("click", () => {
        tocDetails.open = !tocDetails.open;
        if (tocDetails.open) {
          aside.scrollIntoView({ block: "start" });
          tocDetails.querySelector(".learn-toc__home").focus({ preventScroll: true });
        }
      });
      tocDetails.addEventListener("toggle", () => tocButton.setAttribute("aria-expanded", String(tocDetails.open)));
      tocButton.setAttribute("aria-expanded", String(tocDetails.open));
      controls.appendChild(tocButton);
    }
    const label = el("label", "learn-theme-label", "화면");
    const select = el("select", "learn-theme-select");
    select.setAttribute("aria-label", "화면 테마");
    [["system", "기기 설정"], ["light", "라이트"], ["dark", "다크"]].forEach(([value, text]) => {
      const option = el("option", "", text);
      option.value = value;
      select.appendChild(option);
    });
    select.value = window.learnTheme.get();
    select.addEventListener("change", () => window.learnTheme.set(select.value));
    window.addEventListener("learn-theme-change", () => { select.value = window.learnTheme.get(); });
    label.appendChild(select);
    controls.appendChild(label);
    toolbar.appendChild(controls);
    page.insertBefore(toolbar, page.firstChild);

    const dialog = el("dialog", "learn-chart-dialog");
    const heading = el("h2", "", "도표 크게 보기");
    heading.id = "learn-chart-dialog-title";
    dialog.setAttribute("aria-labelledby", heading.id);
    const close = el("button", "learn-reader-close", "닫기");
    close.type = "button";
    const dialogHeader = el("div", "learn-chart-dialog-header");
    dialogHeader.append(heading, close);
    const content = el("div", "learn-chart-dialog-content");
    content.tabIndex = 0;
    content.setAttribute("aria-label", "확대한 도표 · 가로로 넘겨 보기");
    dialog.append(dialogHeader, content);
    document.body.appendChild(dialog);
    let opener;
    close.addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => { document.body.classList.remove("learn-dialog-open"); opener?.focus({ preventScroll: true }); });
    page.querySelectorAll(".learn-chart > svg").forEach((svg, index) => {
      const figure = svg.parentElement;
      const name = svg.querySelector("title")?.textContent || `도표 ${index + 1}`;
      const viewport = el("div", "learn-chart-viewport");
      viewport.tabIndex = 0;
      viewport.setAttribute("role", "region");
      viewport.setAttribute("aria-label", `${name} · 좁은 화면에서는 가로로 넘겨 보기`);
      svg.before(viewport);
      viewport.appendChild(svg);
      const zoom = el("button", "learn-chart-zoom", "크게 보기 ↗");
      zoom.type = "button";
      zoom.setAttribute("aria-label", `${name} 크게 보기`);
      viewport.before(zoom);
      zoom.addEventListener("click", () => {
        opener = zoom;
        heading.textContent = name;
        const clone = svg.cloneNode(true);
        // Dialog clones must not duplicate SVG accessibility or paint-server IDs.
        const idMap = new Map([...clone.querySelectorAll("[id]")].map(node => [node.id, `reader-${index}-${node.id}`]));
        clone.querySelectorAll("*").forEach(node => {
          [...node.attributes].forEach(attr => {
            let value = attr.value;
            if (attr.name === "id") value = idMap.get(value) || value;
            else if (["aria-labelledby", "aria-describedby"].includes(attr.name)) value = value.split(/\s+/).map(id => idMap.get(id) || id).join(" ");
            else idMap.forEach((next, id) => { value = value.replaceAll(`url(#${id})`, `url(#${next})`); });
            node.setAttribute(attr.name, value);
          });
        });
        clone.setAttribute("aria-labelledby", (svg.getAttribute("aria-labelledby") || "").split(/\s+/).map(id => idMap.get(id) || id).join(" "));
        content.replaceChildren(clone);
        const caption = figure.querySelector("figcaption");
        if (caption) content.appendChild(el("p", "learn-chart__caption", caption.textContent));
        dialog.showModal();
        document.body.classList.add("learn-dialog-open");
      });
    });
    page.querySelectorAll("table").forEach(table => {
      if (table.closest(".learn-data, .learn-table-scroll")) return;
      const wrapper = el("div", "learn-table-scroll");
      table.before(wrapper);
      wrapper.appendChild(table);
    });
    page.querySelectorAll(".learn-data, .learn-table-scroll").forEach(wrapper => {
      wrapper.tabIndex = 0;
      wrapper.setAttribute("role", "region");
      wrapper.setAttribute("aria-label", "자료 표 · 가로로 넘겨 보기");
    });
  }

  function init() {
    const page = document.querySelector(".page");
    if (!page || page.dataset.learnTocInit === "1") return;
    page.dataset.learnTocInit = "1";
    page.classList.add("learn-stats--with-sidebar");

    const slug = currentSlug();
    const article = page.querySelector(".learn-chapter");
    const roadmap = page.querySelector(".learn-roadmap");
    const header = page.querySelector(":scope > header.hero");

    const layout = el("div", "learn-layout");
    const aside = el("aside", "learn-toc");
    aside.setAttribute("aria-label", "목차");
    const inner = el("div", "learn-toc__inner");
    const main = el("div", "learn-main");

    [...page.childNodes].forEach((node) => {
      if (node !== header) main.appendChild(node);
    });

    if (roadmap) {
      aside.classList.add("learn-toc--roadmap");
      buildRoadmapList(inner);
    } else if (article) {
      aside.classList.add("learn-toc--chapter");
      ensureSectionIds(article);
      const sectionNav = buildSectionList(inner, article);
      const course = el("details", "learn-course-details");
      course.appendChild(el("summary", "", "전체 과정 목차"));
      buildChapterList(course, slug);
      inner.appendChild(course);
      requestAnimationFrame(() => setupScrollSpy(sectionNav));
    } else {
      aside.classList.add("learn-toc--roadmap");
      buildChapterList(inner, slug);
    }

    const home = document.createElement("a");
    home.href = BASE;
    home.className = "learn-toc__home";
    home.textContent = "← 통계학 & 데이터 분석";
    inner.insertBefore(home, inner.firstChild);

    const tocDetails = el("details", "learn-toc-details");
    const tocSummary = el("summary", "learn-toc-toggle", "목차 열기 · 이 장 / 전체 과정");
    tocDetails.append(tocSummary, inner);
    const compact = window.matchMedia("(max-width: 899px)");
    const syncToc = () => { tocDetails.open = !compact.matches; };
    compact.addEventListener("change", syncToc);
    syncToc();
    aside.appendChild(tocDetails);
    inner.addEventListener("click", (event) => {
      if (compact.matches && event.target.closest("a[data-toc-target]")) tocDetails.open = false;
    });
    layout.appendChild(main);
    layout.appendChild(aside);
    page.appendChild(layout);
    setupReader(page, aside, tocDetails);

    const filter = page.querySelector(".learn-core-filter");
    if (filter && roadmap) {
      filter.hidden = false;
      filter.addEventListener("click", () => {
        const coreOnly = filter.getAttribute("aria-pressed") !== "true";
        filter.setAttribute("aria-pressed", String(coreOnly));
        page.querySelectorAll("li[data-macro-relevance]").forEach((li) => {
          li.hidden = coreOnly && li.dataset.macroRelevance !== "3";
        });
        page.querySelectorAll(".learn-roadmap__group, .learn-toc__group").forEach((group) => {
          group.hidden = !group.querySelector("li:not([hidden])");
        });
        const count = ROADMAP.flatMap((group) => group.items).filter((item) => !coreOnly || item.macro_relevance === 3).length;
        page.querySelector(".learn-filter-status").textContent = coreOnly ? `핵심 ${count}개 장 표시 · 기존 장 순서 유지` : `전체 ${count}개 장`;
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
