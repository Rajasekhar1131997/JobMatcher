const jobsGrid = document.getElementById("jobsGrid");
const emptyState = document.getElementById("emptyState");
const searchInput = document.getElementById("searchInput");
const payFilter = document.getElementById("payFilter");
const distanceFilter = document.getElementById("distanceFilter");

// Configure your Job Service here (or via a query param ?api=...)
const DEFAULT_API = "http://localhost:8000"; // using local WhatsApp service /jobs for now
const urlParams = new URLSearchParams(window.location.search);
const JOB_SERVICE = urlParams.get("api") || DEFAULT_API;
const REF_CODE = urlParams.get("ref");

// Fallback mock data if no API or fetch fails
const fallbackJobs = [
  {
    id: "1",
    title: "Cashier",
    company: "Sunny Market",
    pay: "$18/hr",
    pay_min: 18,
    location: "San Francisco, CA",
    distance_mi: 2,
    shift: "Mon-Fri 4pm-10pm",
    description: "Evening cashier for a neighborhood grocery. Friendly and quick with POS.",
    source: "WhatsApp",
  },
  {
    id: "2",
    title: "Barista",
    company: "Moonlight Cafe",
    pay: "$20/hr",
    pay_min: 20,
    location: "Oakland, CA",
    distance_mi: 9,
    shift: "Sat-Sun 7am-1pm",
    description: "Craft coffee, latte art a plus. Weekend shifts only.",
    source: "Scraped",
  },
  {
    id: "3",
    title: "Prep Cook",
    company: "Taqueria Verde",
    pay: "$22/hr",
    pay_min: 22,
    location: "Berkeley, CA",
    distance_mi: 6,
    shift: "Thu-Sun 3pm-11pm",
    description: "Chopping, grilling, line support. Bilingual preferred.",
    source: "WhatsApp",
  },
];

let jobs = [];

function renderJobs(list) {
  jobsGrid.innerHTML = "";
  if (!list.length) {
    emptyState.classList.remove("hidden");
    return;
  }
  emptyState.classList.add("hidden");

  const tmpl = document.getElementById("jobCardTemplate");
  list.forEach((job) => {
    const node = tmpl.content.cloneNode(true);
    node.querySelector(".pill--source").textContent = job.source || "Job";
    node.querySelector(".card__title").textContent = job.title;
    node.querySelector(".card__company").textContent = job.company;
    node.querySelector(".card__pay").textContent = job.pay;
    node.querySelector(".card__meta").textContent = job.location;
    node.querySelector(".card__desc").textContent = job.description;
    node.querySelector(".pill--shift").textContent = job.shift;
    node.querySelector(".pill--distance").textContent = job.distance_mi ? `${job.distance_mi} mi` : "Nearby";
    node.querySelector(".cta").onclick = () => {
      if (job.apply_url) {
        window.open(job.apply_url, "_blank");
        return;
      }
      if (job.whatsapp_number) {
        const text = encodeURIComponent(`Hi, I'm interested in the ${job.title} role at ${job.company}.`);
        const url = `https://wa.me/${job.whatsapp_number.replace("whatsapp:", "").replace("+", "")}?text=${text}`;
        window.open(url, "_blank");
        return;
      }
      window.alert(`Apply to ${job.title} @ ${job.company} (no apply link provided).`);
    };
    jobsGrid.appendChild(node);
  });
}

function applyFilters() {
  const search = searchInput.value.toLowerCase();
  const payMin = parseFloat(payFilter.value || "0");
  const distanceMax = parseFloat(distanceFilter.value || "0");
  const filtered = jobs.filter((job) => {
    const matchesSearch =
      !search ||
      job.title.toLowerCase().includes(search) ||
      job.company.toLowerCase().includes(search) ||
      job.location.toLowerCase().includes(search);
    const matchesPay = !payMin || job.pay_min >= payMin;
    const matchesDistance = !distanceMax || job.distance_mi <= distanceMax;
    return matchesSearch && matchesPay && matchesDistance;
  });
  renderJobs(filtered);
}

searchInput.addEventListener("input", applyFilters);
payFilter.addEventListener("change", applyFilters);
distanceFilter.addEventListener("change", applyFilters);

async function loadJobs() {
  if (!JOB_SERVICE) {
    jobs = fallbackJobs;
    renderJobs(jobs);
    return;
  }
  try {
    const resp = await fetch(`${JOB_SERVICE}/jobs`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    let mapped = mapJobs(data);
    if (REF_CODE) {
      mapped = mapped.filter((j) => j.confirmation_code === REF_CODE);
    }
    jobs = mapped;
  } catch (err) {
    console.warn("Falling back to mock jobs:", err);
    jobs = fallbackJobs;
  }
  renderJobs(jobs);
}

function mapJobs(apiData) {
  // Expecting array of jobs; adjust mapping as needed.
  if (!Array.isArray(apiData)) return [];
  return apiData.map((j, idx) => ({
    id: j.id || `job-${idx}`,
    confirmation_code: j.confirmation_code || j.ref || null,
    title: j.title || "Role",
    company: j.company_name || j.business_name || "Business",
    pay: j.pay_display || j.pay_rate || "",
    pay_min: j.pay_min || j.pay_rate_min || 0,
    location: j.location || j.location_city || "",
    distance_mi: j.distance_mi || "",
    shift: j.shift || j.shift_times || "",
    description: j.description || "",
    source: j.source || j.channel || j.source_channel || "Job",
    apply_url: j.apply_url || null,
    whatsapp_number: j.contact_phone || null,
    pay_type: j.pay_type || j.payment_type || "",
    images: j.images || j.media_urls || [],
  }));
}

// No-op placeholder to avoid reference errors when modal is disabled.
function closeModal() {}

loadJobs();
