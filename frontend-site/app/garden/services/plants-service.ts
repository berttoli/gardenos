import type { IconName, MetricTone, PageMetric, ShellTone } from "../shared";
import type { GardenServiceContext } from "./context";

export type PlantFilterId = "all" | "review" | "recent" | "lifecycle";
export type PlantViewId = "current" | "history" | "lifecycle";

export type PlantHistoryReply = {
  author: string;
  body: string;
  meta: string;
  icon: IconName;
  tone: ShellTone;
};

export type PlantHistoryEntry = {
  icon: IconName;
  tone: ShellTone;
  title: string;
  detail: string;
  meta: string;
  reply?: PlantHistoryReply;
};

export type PlantLifecycleStage = {
  label: string;
  detail: string;
  meta: string;
  icon: IconName;
  tone: ShellTone;
  active?: boolean;
};

export type PlantProfileId =
  | "camellia-japonica"
  | "acer-palmatum"
  | "monstera-deliciosa"
  | "lavandula-angustifolia"
  | "begonia-rex"
  | "ficus-lyrata"
  | "salvia-greggii";

export type PlantProfile = {
  statusLabel: string;
  statusDetail: string;
  currentPhoto?: {
    src: string;
    alt: string;
    caption?: string;
    meta?: string;
  };
  currentMetrics: PageMetric[];
  history: PlantHistoryEntry[];
  lifecycle: PlantLifecycleStage[];
  noteLabel: string;
  noteBody: string;
  noteMeta: string;
  actions: ReadonlyArray<{ label: string; primary?: boolean; icon?: IconName }>;
};

export type PlantInventoryRecord = {
  id: string;
  profileId: PlantProfileId;
  name: string;
  species: string;
  zone: string;
  status: string;
  statusTone: MetricTone;
  stage: string;
  lastSeen: string;
  nextAction: string;
  note: string;
  icon: IconName;
  tone: ShellTone;
  filters: PlantFilterId[];
  selected?: boolean;
};

export type PlantFilterButton = {
  id: PlantFilterId;
  label: string;
  count: string;
  icon: IconName;
  tone: MetricTone;
};

export type PlantsWorkspaceModel = {
  serviceMeta: {
    name: string;
    version: string;
    scope: string;
  };
  summaryStats: PageMetric[];
  inventoryFilters: PlantFilterButton[];
  inventory: PlantInventoryRecord[];
  profiles: Record<PlantProfileId, PlantProfile>;
};

const currentActionSet = [
  { label: "Log care", primary: true, icon: "notebook" as const },
  { label: "Schedule water", icon: "water" as const },
  { label: "Create task", icon: "add" as const },
] as const;

const reviewActionSet = [
  { label: "Add note", primary: true, icon: "notebook" as const },
  { label: "Attach photo", icon: "camera" as const },
  { label: "Reconcile tag", icon: "inventory" as const },
] as const;

const lifecycleActionSet = [
  { label: "Advance stage", primary: true, icon: "layers" as const },
  { label: "Move zone", icon: "map" as const },
  { label: "Create task", icon: "tasks" as const },
] as const;

const camelliaProfile: PlantProfile = {
  statusLabel: "Healthy",
  statusDetail: "Stable canopy and moisture",
  currentMetrics: [
    {
      kind: "metric",
      label: "Health score",
      value: "94%",
      status: "Stable",
      detail: "No pressure on the canopy",
      icon: "health",
      tone: "sage",
      progress: 94,
    },
    {
      kind: "metric",
      label: "Soil moisture",
      value: "61%",
      status: "Balanced",
      detail: "Within ideal range",
      icon: "droplet",
      tone: "forest",
      progress: 61,
    },
    {
      kind: "metric",
      label: "Canopy light",
      value: "72%",
      status: "Ideal",
      detail: "Shade cloth at 40%",
      icon: "spark",
      tone: "sky",
      progress: 72,
    },
    {
      kind: "metric",
      label: "Next care",
      value: "2h",
      status: "Ready",
      detail: "Morning route",
      icon: "clock",
      tone: "amber",
      progress: 58,
    },
  ],
  history: [
    {
      icon: "water",
      tone: "sky",
      title: "Watered on route",
      detail: "Drip cycle restored moisture to 61% in bench 3A.",
      meta: "Today · 7:42 AM",
      reply: {
        author: "Luis M.",
        body: "Kept the canopy dry and logged the bed as stable.",
        meta: "Added 4 min later",
        icon: "notebook",
        tone: "forest",
      },
    },
    {
      icon: "camera",
      tone: "sage",
      title: "Photo matched label",
      detail: "Leaf shape and bloom stage confirmed against the field record.",
      meta: "Yesterday · 4:15 PM",
      reply: {
        author: "Jordan",
        body: "No pest pressure, just a little edge curl from the afternoon heat.",
        meta: "Crew note",
        icon: "health",
        tone: "sage",
      },
    },
    {
      icon: "inventory",
      tone: "amber",
      title: "Transferred from propagation",
      detail: "Moved into the active greenhouse bench and tagged to GH1.",
      meta: "Aug 6 · 9:10 AM",
    },
    {
      icon: "notebook",
      tone: "forest",
      title: "Inventory reconciliation",
      detail: "Barcode matched the zone record after the morning scan.",
      meta: "Aug 4 · 2:20 PM",
    },
  ],
  lifecycle: [
    {
      label: "Propagation",
      detail: "Bench rooted and ready for hardening.",
      meta: "Complete",
      icon: "spark",
      tone: "forest",
    },
    {
      label: "Transplant",
      detail: "Moved to greenhouse bench 1 with shade support.",
      meta: "Active stage",
      icon: "layers",
      tone: "sage",
      active: true,
    },
    {
      label: "Establishment",
      detail: "Watch for the next growth flush and canopy settle.",
      meta: "Next",
      icon: "leaf",
      tone: "sky",
    },
    {
      label: "Maintenance",
      detail: "Light prune and weekly irrigation checks.",
      meta: "Upcoming",
      icon: "water",
      tone: "amber",
    },
  ],
  noteLabel: "Field note",
  noteBody: "Keep the plant on the north bench through the afternoon and review leaf edge curl after the next irrigation cycle.",
  noteMeta: "Updated 13:11 by Jordan",
  actions: currentActionSet,
};

const acerProfile: PlantProfile = {
  statusLabel: "Watch",
  statusDetail: "Moisture trending low",
  currentMetrics: [
    {
      kind: "metric",
      label: "Health score",
      value: "78%",
      status: "Watch",
      detail: "Leaf margin stress starting",
      icon: "health",
      tone: "amber",
      progress: 78,
    },
    {
      kind: "metric",
      label: "Soil moisture",
      value: "18%",
      status: "Low",
      detail: "Needs irrigation soon",
      icon: "droplet",
      tone: "sky",
      progress: 18,
    },
    {
      kind: "metric",
      label: "Canopy light",
      value: "54%",
      status: "Good",
      detail: "Under shade cloth",
      icon: "spark",
      tone: "forest",
      progress: 54,
    },
    {
      kind: "metric",
      label: "Next care",
      value: "30m",
      status: "Urgent",
      detail: "Needs water on next pass",
      icon: "water",
      tone: "amber",
      progress: 22,
    },
  ],
  history: [
    {
      icon: "water",
      tone: "amber",
      title: "Moisture check flagged",
      detail: "Soil probe fell below target band in GH2.",
      meta: "Today · 8:04 AM",
      reply: {
        author: "Sarah K.",
        body: "Marked for the next irrigation cycle and kept it on the review bench.",
        meta: "Follow-up",
        icon: "alert",
        tone: "amber",
      },
    },
    {
      icon: "camera",
      tone: "sage",
      title: "Canopy photo reviewed",
      detail: "Color remains good, but edges are starting to crisp.",
      meta: "Yesterday · 3:22 PM",
    },
    {
      icon: "inventory",
      tone: "forest",
      title: "Zone transfer queued",
      detail: "Preparing to move from propagation to transplant row.",
      meta: "Aug 7 · 10:10 AM",
    },
  ],
  lifecycle: [
    {
      label: "Propagation",
      detail: "Rooting bench still active, keep moisture high.",
      meta: "Complete",
      icon: "spark",
      tone: "forest",
    },
    {
      label: "Transplant",
      detail: "Waiting for a better moisture window before moving.",
      meta: "Active stage",
      icon: "layers",
      tone: "amber",
      active: true,
    },
    {
      label: "Establishment",
      detail: "Will need a full week of observation after move.",
      meta: "Next",
      icon: "leaf",
      tone: "sky",
    },
  ],
  noteLabel: "Review note",
  noteBody: "Water this bench before midday and recheck leaf turgor tomorrow morning.",
  noteMeta: "Updated 13:11 by Sarah",
  actions: reviewActionSet,
};

const monsteraProfile: PlantProfile = {
  statusLabel: "Good",
  statusDetail: "Strong growth pattern",
  currentMetrics: [
    {
      kind: "metric",
      label: "Health score",
      value: "88%",
      status: "Good",
      detail: "Leaf count trending up",
      icon: "health",
      tone: "sage",
      progress: 88,
    },
    {
      kind: "metric",
      label: "Soil moisture",
      value: "66%",
      status: "Balanced",
      detail: "Regular watering cadence",
      icon: "droplet",
      tone: "forest",
      progress: 66,
    },
    {
      kind: "metric",
      label: "Canopy light",
      value: "81%",
      status: "Ideal",
      detail: "Bright but not harsh",
      icon: "spark",
      tone: "sky",
      progress: 81,
    },
    {
      kind: "metric",
      label: "Next care",
      value: "Tomorrow",
      status: "Ready",
      detail: "Rotate pot and dust leaves",
      icon: "clock",
      tone: "amber",
      progress: 44,
    },
  ],
  history: [
    {
      icon: "water",
      tone: "sky",
      title: "Watered in shade house",
      detail: "Moisture reset after the morning cycle.",
      meta: "Today · 6:55 AM",
    },
    {
      icon: "notebook",
      tone: "forest",
      title: "Leaves wiped and rotated",
      detail: "Plant is turning toward the south windows more evenly now.",
      meta: "Yesterday · 5:10 PM",
      reply: {
        author: "Jordan",
        body: "Keep an eye on the aerial roots after the next scan.",
        meta: "Crew note",
        icon: "leaf",
        tone: "forest",
      },
    },
    {
      icon: "camera",
      tone: "sage",
      title: "Growth photo logged",
      detail: "New fenestration visible on the upper leaf.",
      meta: "Aug 5 · 11:18 AM",
    },
  ],
  lifecycle: [
    {
      label: "Rooted",
      detail: "Stable base and ready for a larger pot.",
      meta: "Complete",
      icon: "spark",
      tone: "forest",
    },
    {
      label: "Established",
      detail: "Strong leaf expansion and regular watering.",
      meta: "Active stage",
      icon: "leaf",
      tone: "sage",
      active: true,
    },
    {
      label: "Canopy build",
      detail: "Train aerial roots and rotate weekly.",
      meta: "Upcoming",
      icon: "layers",
      tone: "sky",
    },
  ],
  noteLabel: "Growth note",
  noteBody: "Keep the plant near filtered light and rotate after the afternoon scan.",
  noteMeta: "Updated 13:11 by Mona",
  actions: currentActionSet,
};

const lavenderProfile: PlantProfile = {
  statusLabel: "Healthy",
  statusDetail: "Dry bed, full sun",
  currentMetrics: [
    {
      kind: "metric",
      label: "Health score",
      value: "91%",
      status: "Healthy",
      detail: "Flowering and compact",
      icon: "health",
      tone: "sage",
      progress: 91,
    },
    {
      kind: "metric",
      label: "Soil moisture",
      value: "47%",
      status: "Balanced",
      detail: "Drying between cycles",
      icon: "droplet",
      tone: "sky",
      progress: 47,
    },
    {
      kind: "metric",
      label: "Canopy light",
      value: "88%",
      status: "Ideal",
      detail: "Full sun exposure",
      icon: "spark",
      tone: "forest",
      progress: 88,
    },
    {
      kind: "metric",
      label: "Next care",
      value: "Afternoon",
      status: "Ready",
      detail: "Light prune after route",
      icon: "clock",
      tone: "amber",
      progress: 66,
    },
  ],
  history: [
    {
      icon: "water",
      tone: "sage",
      title: "Bed watered lightly",
      detail: "Kept the root zone from drying out between checks.",
      meta: "Today · 6:30 AM",
    },
    {
      icon: "notebook",
      tone: "forest",
      title: "Flower count logged",
      detail: "Peak bloom is still ahead, but the first flush is visible.",
      meta: "Yesterday · 1:45 PM",
    },
    {
      icon: "camera",
      tone: "sky",
      title: "Tag and photo synced",
      detail: "Barcode and bed image matched the inventory record.",
      meta: "Aug 4 · 9:02 AM",
    },
  ],
  lifecycle: [
    {
      label: "Establishment",
      detail: "Root system stable, handle with minimal disturbance.",
      meta: "Complete",
      icon: "leaf",
      tone: "forest",
    },
    {
      label: "Flowering",
      detail: "Peak bloom window is opening across the row.",
      meta: "Active stage",
      icon: "spark",
      tone: "sage",
      active: true,
    },
    {
      label: "Maintenance",
      detail: "Deadhead and keep a short dry interval.",
      meta: "Next",
      icon: "water",
      tone: "amber",
    },
  ],
  noteLabel: "Sun note",
  noteBody: "Keep the bed open to the morning sun and avoid overwatering the roots.",
  noteMeta: "Updated 13:11 by Mia",
  actions: reviewActionSet,
};

const begoniaProfile: PlantProfile = {
  statusLabel: "Rooting",
  statusDetail: "Propagation tray active",
  currentMetrics: [
    {
      kind: "metric",
      label: "Health score",
      value: "83%",
      status: "Rooting",
      detail: "New leaf still curled",
      icon: "health",
      tone: "forest",
      progress: 83,
    },
    {
      kind: "metric",
      label: "Soil moisture",
      value: "69%",
      status: "Balanced",
      detail: "Tray stays humid",
      icon: "droplet",
      tone: "sky",
      progress: 69,
    },
    {
      kind: "metric",
      label: "Canopy light",
      value: "61%",
      status: "Ideal",
      detail: "Filtered light only",
      icon: "spark",
      tone: "sage",
      progress: 61,
    },
    {
      kind: "metric",
      label: "Next care",
      value: "Transplant",
      status: "Ready",
      detail: "Move to a larger cell tray",
      icon: "layers",
      tone: "amber",
      progress: 40,
    },
  ],
  history: [
    {
      icon: "inventory",
      tone: "amber",
      title: "Prop tray updated",
      detail: "New root batch moved from the propagation shelf.",
      meta: "Today · 8:34 AM",
      reply: {
        author: "Emma",
        body: "Leave another day before the cell tray move.",
        meta: "Crew note",
        icon: "clock",
        tone: "amber",
      },
    },
    {
      icon: "camera",
      tone: "sage",
      title: "Root check photo saved",
      detail: "White root tips visible under the tray liner.",
      meta: "Yesterday · 2:12 PM",
    },
    {
      icon: "notebook",
      tone: "forest",
      title: "Humidity was raised",
      detail: "Humidity dome restored after the afternoon drop.",
      meta: "Aug 7 · 9:45 AM",
    },
  ],
  lifecycle: [
    {
      label: "Propagation",
      detail: "Tray rooted and under humidity control.",
      meta: "Active stage",
      icon: "spark",
      tone: "sage",
      active: true,
    },
    {
      label: "Transplant",
      detail: "Move once the root crown is fully white.",
      meta: "Next",
      icon: "layers",
      tone: "amber",
    },
    {
      label: "Establishment",
      detail: "Monitor for a week after move.",
      meta: "Upcoming",
      icon: "leaf",
      tone: "sky",
    },
  ],
  noteLabel: "Propagation note",
  noteBody: "Keep the humidity dome on until the next transplant window opens.",
  noteMeta: "Updated 13:11 by Emma",
  actions: lifecycleActionSet,
};

const ficusProfile: PlantProfile = {
  statusLabel: "Watch",
  statusDetail: "Needs a larger pot",
  currentMetrics: [
    {
      kind: "metric",
      label: "Health score",
      value: "76%",
      status: "Watch",
      detail: "Top growth is steady",
      icon: "health",
      tone: "amber",
      progress: 76,
    },
    {
      kind: "metric",
      label: "Soil moisture",
      value: "42%",
      status: "Balanced",
      detail: "Water before noon tomorrow",
      icon: "droplet",
      tone: "forest",
      progress: 42,
    },
    {
      kind: "metric",
      label: "Canopy light",
      value: "57%",
      status: "Good",
      detail: "Still under indirect light",
      icon: "spark",
      tone: "sky",
      progress: 57,
    },
    {
      kind: "metric",
      label: "Next care",
      value: "Repot",
      status: "Urgent",
      detail: "Move to 14 in. pot",
      icon: "inventory",
      tone: "amber",
      progress: 35,
    },
  ],
  history: [
    {
      icon: "inventory",
      tone: "amber",
      title: "Pot restriction noted",
      detail: "Root ball is starting to hold moisture too long.",
      meta: "Today · 10:20 AM",
    },
    {
      icon: "camera",
      tone: "sage",
      title: "Branch spread photo",
      detail: "Growth remains symmetrical, but canopy is getting tight.",
      meta: "Yesterday · 4:50 PM",
    },
    {
      icon: "notebook",
      tone: "forest",
      title: "Zone assignment confirmed",
      detail: "Container Yard match is current and valid.",
      meta: "Aug 3 · 8:12 AM",
    },
  ],
  lifecycle: [
    {
      label: "Establishment",
      detail: "Stable but nearing the end of the current pot size.",
      meta: "Active stage",
      icon: "leaf",
      tone: "sage",
      active: true,
    },
    {
      label: "Repotting",
      detail: "Shift to the larger pot before the next watering cycle.",
      meta: "Next",
      icon: "inventory",
      tone: "amber",
    },
    {
      label: "Canopy build",
      detail: "Allow new growth to harden before pruning.",
      meta: "Upcoming",
      icon: "spark",
      tone: "sky",
    },
  ],
  noteLabel: "Repot note",
  noteBody: "Move this plant into a larger pot before the weekend route.",
  noteMeta: "Updated 13:11 by Luis",
  actions: reviewActionSet,
};

const salviaProfile: PlantProfile = {
  statusLabel: "Good",
  statusDetail: "Flowering in the field",
  currentMetrics: [
    {
      kind: "metric",
      label: "Health score",
      value: "89%",
      status: "Good",
      detail: "Blooms are even across the row",
      icon: "health",
      tone: "sage",
      progress: 89,
    },
    {
      kind: "metric",
      label: "Soil moisture",
      value: "55%",
      status: "Balanced",
      detail: "Holding steady after sunrise",
      icon: "droplet",
      tone: "forest",
      progress: 55,
    },
    {
      kind: "metric",
      label: "Canopy light",
      value: "84%",
      status: "Ideal",
      detail: "Full sun through midday",
      icon: "spark",
      tone: "sky",
      progress: 84,
    },
    {
      kind: "metric",
      label: "Next care",
      value: "Late AM",
      status: "Ready",
      detail: "Quick deadhead pass",
      icon: "clock",
      tone: "amber",
      progress: 63,
    },
  ],
  history: [
    {
      icon: "water",
      tone: "sky",
      title: "Morning water run",
      detail: "Field row stayed evenly moist after sunrise.",
      meta: "Today · 6:48 AM",
    },
    {
      icon: "camera",
      tone: "sage",
      title: "Bloom sequence recorded",
      detail: "Flowering is running on schedule across the row.",
      meta: "Yesterday · 11:12 AM",
    },
    {
      icon: "notebook",
      tone: "forest",
      title: "Row audit completed",
      detail: "No missing labels or zone mismatches found.",
      meta: "Aug 5 · 3:40 PM",
    },
  ],
  lifecycle: [
    {
      label: "Establishment",
      detail: "Rooted and holding after the last move.",
      meta: "Complete",
      icon: "leaf",
      tone: "forest",
    },
    {
      label: "Flowering",
      detail: "Peak bloom window is open now.",
      meta: "Active stage",
      icon: "spark",
      tone: "sage",
      active: true,
    },
    {
      label: "Maintenance",
      detail: "Deadhead and keep the sun exposure even.",
      meta: "Upcoming",
      icon: "water",
      tone: "amber",
    },
  ],
  noteLabel: "Field note",
  noteBody: "This row is good; just keep the deadheading pass on the morning route.",
  noteMeta: "Updated 13:11 by field ops",
  actions: currentActionSet,
};

export const plantServiceMeta = {
  name: "Plant service",
  version: "v1",
  scope: "Inventory + lifecycle",
} as const;

export const plantSummaryStats: PageMetric[] = [
  {
    kind: "metric",
    label: "Tracked plants",
    value: "1,248",
    status: "+18 this week",
    detail: "Across 14 active zones",
    icon: "plants",
    tone: "sage",
    progress: 86,
  },
  {
    kind: "metric",
    label: "Healthy plants",
    value: "842",
    status: "67.6%",
    detail: "Stable canopy coverage",
    icon: "health",
    tone: "forest",
    progress: 67,
  },
  {
    kind: "metric",
    label: "Needs attention",
    value: "126",
    status: "10.1%",
    detail: "Irrigation or exposure follow-up",
    icon: "alert",
    tone: "amber",
    progress: 10,
  },
  {
    kind: "metric",
    label: "Needs review",
    value: "42",
    status: "3.4%",
    detail: "Missing zones or labels",
    icon: "inventory",
    tone: "amber",
    progress: 42,
  },
  {
    kind: "metric",
    label: "Recent scans",
    value: "118",
    status: "Live",
    detail: "Last 24 hours",
    icon: "search",
    tone: "sky",
    progress: 74,
  },
];

export const plantInventoryFilters: PlantFilterButton[] = [
  { id: "all", label: "All plants", count: "7", icon: "inventory", tone: "forest" },
  { id: "review", label: "Needs review", count: "3", icon: "alert", tone: "amber" },
  { id: "recent", label: "Recently scanned", count: "4", icon: "camera", tone: "sage" },
  { id: "lifecycle", label: "Lifecycle alerts", count: "3", icon: "layers", tone: "sky" },
];

export const plantInventory: PlantInventoryRecord[] = [
  {
    id: "camellia-japonica",
    profileId: "camellia-japonica",
    name: "Camellia japonica",
    species: "Evergreen shrub",
    zone: "GH1",
    status: "Healthy",
    statusTone: "sage",
    stage: "Transplant",
    lastSeen: "2h ago",
    nextAction: "Light prune this morning",
    note: "Stable after the latest irrigation pass.",
    icon: "plants",
    tone: "sage",
    filters: ["all", "recent", "lifecycle"],
    selected: true,
  },
  {
    id: "acer-palmatum",
    profileId: "acer-palmatum",
    name: "Japanese maple",
    species: "Acer palmatum",
    zone: "GH2",
    status: "Watch",
    statusTone: "amber",
    stage: "Transplant",
    lastSeen: "18m ago",
    nextAction: "Irrigate on next route",
    note: "Moisture trending low near the north wall.",
    icon: "inventory",
    tone: "amber",
    filters: ["all", "review"],
  },
  {
    id: "monstera-deliciosa",
    profileId: "monstera-deliciosa",
    name: "Monstera deliciosa",
    species: "Tropical foliage",
    zone: "Shade House",
    status: "Good",
    statusTone: "forest",
    stage: "Established",
    lastSeen: "1h ago",
    nextAction: "Rotate toward filtered light",
    note: "New fenestration visible on the top leaf.",
    icon: "leaf",
    tone: "forest",
    filters: ["all", "recent"],
  },
  {
    id: "lavandula-angustifolia",
    profileId: "lavandula-angustifolia",
    name: "Lavandula angustifolia",
    species: "Field lavender",
    zone: "Outdoor Rows",
    status: "Healthy",
    statusTone: "sage",
    stage: "Flowering",
    lastSeen: "Today",
    nextAction: "Deadhead after the heat passes",
    note: "Full sun bed staying compact and clean.",
    icon: "spark",
    tone: "sky",
    filters: ["all", "recent"],
  },
  {
    id: "begonia-rex",
    profileId: "begonia-rex",
    name: "Begonia rex",
    species: "Propagation tray",
    zone: "Propagation House",
    status: "Rooting",
    statusTone: "forest",
    stage: "Propagation",
    lastSeen: "22m ago",
    nextAction: "Move to a larger cell tray",
    note: "Humidity dome still holding well.",
    icon: "inventory",
    tone: "sage",
    filters: ["all", "lifecycle", "recent"],
  },
  {
    id: "ficus-lyrata",
    profileId: "ficus-lyrata",
    name: "Ficus lyrata",
    species: "Broadleaf houseplant",
    zone: "Container Yard",
    status: "Watch",
    statusTone: "amber",
    stage: "Established",
    lastSeen: "Yesterday",
    nextAction: "Repot before the weekend",
    note: "Root ball is starting to hold moisture too long.",
    icon: "health",
    tone: "amber",
    filters: ["all", "review", "lifecycle"],
  },
  {
    id: "salvia-greggii",
    profileId: "salvia-greggii",
    name: "Salvia greggii",
    species: "Flowering field row",
    zone: "South Field",
    status: "Good",
    statusTone: "sage",
    stage: "Flowering",
    lastSeen: "30m ago",
    nextAction: "Quick deadhead pass",
    note: "Peak bloom still looks balanced across the row.",
    icon: "water",
    tone: "forest",
    filters: ["all", "recent"],
  },
];

export const plantProfiles: Record<PlantProfileId, PlantProfile> = {
  "camellia-japonica": camelliaProfile,
  "acer-palmatum": acerProfile,
  "monstera-deliciosa": monsteraProfile,
  "lavandula-angustifolia": lavenderProfile,
  "begonia-rex": begoniaProfile,
  "ficus-lyrata": ficusProfile,
  "salvia-greggii": salviaProfile,
};

export const plantControlTabs = [
  { id: "current", label: "Current state", icon: "compass" as const },
  { id: "history", label: "History", icon: "notebook" as const },
  { id: "lifecycle", label: "Lifecycle", icon: "layers" as const },
] as const;

export function getPlantsModel(_context: GardenServiceContext | null = null): PlantsWorkspaceModel {
  void _context;
  return {
    serviceMeta: plantServiceMeta,
    summaryStats: plantSummaryStats,
    inventoryFilters: plantInventoryFilters,
    inventory: plantInventory,
    profiles: plantProfiles,
  };
}
