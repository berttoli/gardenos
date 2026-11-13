"use client";

import { useEffect, useMemo, useState } from "react";

import type { DockTabItem } from "../shared";
import type { GardenServiceContext } from "../services/context";
import {
  Chip,
  DockButtonGroup,
  Icon,
  InspectorMetricCard,
} from "../shared";
import type { PageWorkspaceView } from "./registry";
import { getPlantsModel, type PlantFilterId, type PlantHistoryEntry, type PlantLifecycleStage, type PlantInventoryRecord, type PlantProfile, type PlantViewId } from "../services/plants-service";

const controlTabs: DockTabItem[] = [
  { id: "current", label: "Current state", icon: "compass" },
  { id: "history", label: "History", icon: "notebook" },
  { id: "lifecycle", label: "Lifecycle", icon: "layers" },
];

type PlantPhotoAsset = PlantProfile["currentPhoto"];

function PlantPhotoFrame({
  photo,
  variant,
  eyebrow,
  title,
  caption,
  actionLabel,
  onAction,
}: {
  photo?: PlantPhotoAsset;
  variant: "compact" | "hero";
  eyebrow: string;
  title: string;
  caption: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <figure className="target-plant-photo-frame" data-has-photo={photo ? "true" : "false"} data-variant={variant}>
      <div className="target-plant-photo-media">
        {photo ? (
          <img alt={photo.alt} draggable="false" src={photo.src} />
        ) : (
          <div className="target-plant-photo-shell" role="img" aria-label={`${title} photo placeholder`}>
            <span className="target-plant-photo-shell-orb target-plant-photo-shell-orb-a" />
            <span className="target-plant-photo-shell-orb target-plant-photo-shell-orb-b" />
            <span className="target-plant-photo-shell-orb target-plant-photo-shell-orb-c" />
            <span className="target-plant-photo-shell-leaf">
              <Icon name="leaf" />
            </span>
            <span className="target-plant-photo-shell-camera">
              <Icon name="camera" />
            </span>
          </div>
        )}
      </div>

      <figcaption className="target-plant-photo-copy">
        <span className="section-label">{eyebrow}</span>
        <strong>{photo ? photo.caption ?? title : "No current photo"}</strong>
        <span>{photo ? photo.meta ?? caption : caption}</span>
        {actionLabel ? (
          <button className="target-plant-photo-action" type="button" onClick={onAction}>
            {actionLabel}
          </button>
        ) : null}
      </figcaption>
    </figure>
  );
}

const plantPreviewPalette = {
  sage: {
    bgA: "#f4f7f0",
    bgB: "#dbe7d5",
    leafA: "#6b846c",
    leafB: "#9bb392",
    bloom: "#f7f5ef",
    bloomShade: "#eadfce",
    center: "#d9b85d",
    pollen: "#b67824",
  },
  amber: {
    bgA: "#f6f2e7",
    bgB: "#eadcc0",
    leafA: "#7a8f71",
    leafB: "#a9b58f",
    bloom: "#f8f0d8",
    bloomShade: "#eed7a6",
    center: "#d79a41",
    pollen: "#b36a24",
  },
  forest: {
    bgA: "#eef3ec",
    bgB: "#d5e1d3",
    leafA: "#4d6750",
    leafB: "#7f9a82",
    bloom: "#f4f7f0",
    bloomShade: "#dde8d8",
    center: "#c9d79f",
    pollen: "#7b8d4f",
  },
  sky: {
    bgA: "#eef4f7",
    bgB: "#d6e4ea",
    leafA: "#65808a",
    leafB: "#9fb0b8",
    bloom: "#f1f7fb",
    bloomShade: "#d7e7f0",
    center: "#d6c39a",
    pollen: "#8e6e40",
  },
} as const;

function buildFeaturedPlantPhoto(plant: PlantInventoryRecord): NonNullable<PlantPhotoAsset> {
  const palette = plantPreviewPalette[plant.tone as keyof typeof plantPreviewPalette] ?? plantPreviewPalette.sage;
  const outerPetals = [-42, -6, 30, 66, 102, 138, 174, 210]
    .map(
      (angle, index) =>
        `<ellipse cx="662" cy="246" rx="${index % 2 === 0 ? 58 : 64}" ry="${index % 2 === 0 ? 126 : 138}" fill="${palette.bloom}" opacity="${index % 2 === 0 ? 0.98 : 0.92}" transform="rotate(${angle} 662 350)" />`,
    )
    .join("");

  const innerPetals = [-18, 30, 78, 126, 174, 222]
    .map(
      (angle, index) =>
        `<ellipse cx="662" cy="284" rx="${index % 2 === 0 ? 34 : 40}" ry="${index % 2 === 0 ? 90 : 98}" fill="${palette.bloomShade}" opacity="${index % 2 === 0 ? 0.86 : 0.8}" transform="rotate(${angle} 662 350)" />`,
    )
    .join("");

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 760" role="img" aria-hidden="true">
      <defs>
        <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="${palette.bgA}" />
          <stop offset="100%" stop-color="${palette.bgB}" />
        </linearGradient>
        <radialGradient id="glowA" cx="28%" cy="24%" r="48%">
          <stop offset="0%" stop-color="${palette.bloom}" stop-opacity="0.96" />
          <stop offset="100%" stop-color="${palette.bloom}" stop-opacity="0" />
        </radialGradient>
        <radialGradient id="glowB" cx="72%" cy="78%" r="54%">
          <stop offset="0%" stop-color="${palette.leafB}" stop-opacity="0.42" />
          <stop offset="100%" stop-color="${palette.leafB}" stop-opacity="0" />
        </radialGradient>
        <linearGradient id="leafA" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="${palette.leafB}" />
          <stop offset="100%" stop-color="${palette.leafA}" />
        </linearGradient>
        <linearGradient id="leafB" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="${palette.leafA}" />
          <stop offset="100%" stop-color="${palette.leafB}" />
        </linearGradient>
        <filter id="blur" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="24" />
        </filter>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="12" stdDeviation="18" flood-color="rgba(26, 36, 30, 0.28)" />
        </filter>
      </defs>
      <rect width="1200" height="760" fill="url(#bg)" />
      <circle cx="220" cy="160" r="180" fill="url(#glowA)" filter="url(#blur)" opacity="0.82" />
      <circle cx="950" cy="620" r="250" fill="url(#glowB)" filter="url(#blur)" opacity="0.7" />
      <g opacity="0.95">
        <ellipse cx="260" cy="570" rx="220" ry="84" fill="url(#leafA)" opacity="0.8" transform="rotate(-18 260 570)" />
        <ellipse cx="340" cy="438" rx="180" ry="70" fill="url(#leafB)" opacity="0.74" transform="rotate(-32 340 438)" />
        <ellipse cx="880" cy="310" rx="210" ry="82" fill="url(#leafA)" opacity="0.8" transform="rotate(26 880 310)" />
        <ellipse cx="805" cy="474" rx="152" ry="60" fill="url(#leafB)" opacity="0.72" transform="rotate(16 805 474)" />
      </g>
      <g filter="url(#shadow)">
        ${outerPetals}
        ${innerPetals}
        <circle cx="662" cy="350" r="42" fill="${palette.center}" />
        <circle cx="662" cy="350" r="17" fill="${palette.pollen}" />
        <circle cx="662" cy="350" r="8" fill="#f9f7f2" opacity="0.92" />
      </g>
      <path d="M642 350C612 460 596 544 562 676" fill="none" stroke="${palette.leafA}" stroke-width="10" stroke-linecap="round" opacity="0.9" />
      <path d="M686 350C736 456 764 546 806 674" fill="none" stroke="${palette.leafB}" stroke-width="8" stroke-linecap="round" opacity="0.84" />
    </svg>`;

  return {
    src: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
    alt: `${plant.name} botanical preview`,
    caption: plant.name,
    meta: `${plant.species} · ${plant.zone} · ${plant.stage}`,
  };
}

function PlantInventoryRow({
  plant,
  active,
  onSelect,
}: {
  plant: PlantInventoryRecord;
  active?: boolean;
  onSelect: (plantId: string) => void;
}) {
  return (
    <button
      className="target-plant-row"
      data-selected={active ? "true" : "false"}
      data-tone={plant.statusTone}
      type="button"
      aria-pressed={active}
      onClick={() => onSelect(plant.id)}
    >
      <span className="target-plant-row-main">
        <span className="target-plant-row-icon" data-tone={plant.tone}>
          <Icon name={plant.icon} />
        </span>

        <span className="target-plant-row-copy">
          <strong>{plant.name}</strong>
          <span>{plant.species}</span>
          {active ? <span className="target-plant-row-note">{plant.nextAction}</span> : null}
        </span>
      </span>

      <span className="target-plant-row-state" data-tone={plant.statusTone}>
        {plant.status}
      </span>

      <span className="target-plant-row-meta">
        <span className="target-plant-row-zone">{plant.zone}</span>
        <span className="target-plant-row-seen">{plant.lastSeen}</span>
      </span>

      <Icon name="chevron" className="target-plant-row-chevron" />
    </button>
  );
}

function PlantSpotlightCard({
  plant,
  profile,
  onPlantAction,
}: {
  plant: PlantInventoryRecord;
  profile: PlantProfile;
  onPlantAction: (message: string) => void;
}) {
  const featuredPhoto = profile.currentPhoto ?? buildFeaturedPlantPhoto(plant);

  return (
    <article className="target-plant-spotlight">
      <div className="target-plant-spotlight-head">
        <div className="target-plant-spotlight-identity">
          <span className="target-plant-spotlight-icon" data-tone={plant.tone}>
            <Icon name={plant.icon} />
          </span>

          <div className="target-plant-spotlight-copy">
            <span className="section-label">Selected plant</span>
            <p>
              {plant.species} · {plant.zone} · {plant.stage}
            </p>
          </div>
        </div>

        <Chip icon="health" tone={plant.statusTone} title={profile.statusDetail} ariaLabel={profile.statusDetail}>
          {profile.statusLabel}
        </Chip>
      </div>

      <PlantPhotoFrame
        photo={featuredPhoto}
        variant="hero"
        eyebrow="Featured photo"
        title={plant.name}
        caption={`${plant.species} · ${plant.zone} · ${plant.stage}`}
        actionLabel="View plant"
        onAction={() => onPlantAction(`Opened the featured view for ${plant.name}.`)}
      />

      <div className="target-plant-spotlight-note">
        <span className="target-note-label">{profile.noteLabel}</span>
        <p>{profile.noteBody}</p>
        <div className="target-plant-spotlight-note-meta">{profile.noteMeta}</div>
      </div>
    </article>
  );
}

function PlantSummaryCard({ metric }: { metric: ReturnType<typeof getPlantsModel>["summaryStats"][number] }) {
  return (
    <article className="target-plant-summary-card" data-tone={metric.tone} title={metric.detail}>
      <div className="target-plant-summary-head">
        <span className="target-plant-summary-icon">
          <Icon name={metric.icon} />
        </span>
        <strong>{metric.label}</strong>
        <span className="target-plant-summary-status">{metric.status}</span>
      </div>

      <div className="target-plant-summary-body">
        <strong>{metric.value}</strong>
      </div>
    </article>
  );
}

function PlantHistoryEntryCard({ entry }: { entry: PlantHistoryEntry }) {
  return (
    <article className="target-plant-history-item" data-tone={entry.tone}>
      <span className="target-plant-history-icon" data-tone={entry.tone}>
        <Icon name={entry.icon} />
      </span>

      <div className="target-plant-history-copy">
        <div className="target-plant-history-head">
          <strong>{entry.title}</strong>
          <span>{entry.meta}</span>
        </div>
        <div className="target-plant-history-body">{entry.detail}</div>

        {entry.reply ? (
          <article className="target-plant-history-reply" data-tone={entry.reply.tone}>
            <span className="target-plant-history-reply-icon">
              <Icon name={entry.reply.icon} />
            </span>
            <div className="target-plant-history-reply-copy">
              <strong>{entry.reply.author}</strong>
              <span>{entry.reply.body}</span>
              <em>{entry.reply.meta}</em>
            </div>
          </article>
        ) : null}
      </div>
    </article>
  );
}

function PlantLifecycleStageCard({ stage }: { stage: PlantLifecycleStage }) {
  return (
    <article className="target-plant-lifecycle-stage" data-active={stage.active ? "true" : "false"} data-tone={stage.tone}>
      <span className="target-plant-lifecycle-icon" data-tone={stage.tone}>
        <Icon name={stage.icon} />
      </span>

      <div className="target-plant-lifecycle-copy">
        <div className="target-plant-lifecycle-head">
          <strong>{stage.label}</strong>
          <span>{stage.meta}</span>
        </div>
        <div className="target-plant-lifecycle-body">{stage.detail}</div>
      </div>
    </article>
  );
}

function PlantCurrentView({
  profile,
  selectedPlant,
  onPlantAction,
}: {
  profile: PlantProfile;
  selectedPlant: PlantInventoryRecord;
  onPlantAction: (message: string) => void;
}) {
  return (
    <section className="target-plant-control-view">
      <div className="target-plant-control-head">
        <div className="target-plant-control-copy">
          <span className="section-label">Current state</span>
          <h4>{selectedPlant.name}</h4>
          <p>
            {selectedPlant.species} · {selectedPlant.zone} · {selectedPlant.stage}
          </p>
        </div>

        <Chip icon="health" tone={selectedPlant.statusTone} title={profile.statusDetail} ariaLabel={profile.statusDetail}>
          {profile.statusLabel}
        </Chip>
      </div>

      <PlantPhotoFrame
        caption="Capture a current field shot so the plant record opens with a visual anchor."
        eyebrow="Current photo"
        photo={profile.currentPhoto}
        title={selectedPlant.name}
        variant="compact"
        onAction={() => onPlantAction(`Opened the photo capture flow for ${selectedPlant.name}.`)}
      />

      <div className="target-plant-current-metrics">
        {profile.currentMetrics.map((metric) => (
          <InspectorMetricCard key={metric.label} {...metric} />
        ))}
      </div>

      <article className="target-note-card target-plant-note-card">
        <span className="target-note-label">{profile.noteLabel}</span>
        <div className="target-note-body">
          <strong>{selectedPlant.name}</strong>
          <span>{profile.noteBody}</span>
        </div>
        <div className="target-note-meta">{profile.noteMeta}</div>
      </article>
    </section>
  );
}

function PlantHistoryView({
  profile,
  selectedPlant,
}: {
  profile: PlantProfile;
  selectedPlant: PlantInventoryRecord;
}) {
  return (
    <section className="target-plant-control-view">
      <div className="target-plant-control-head">
        <div className="target-plant-control-copy">
          <span className="section-label">History</span>
          <h4>{selectedPlant.name}</h4>
          <p>Threaded trail of scans, notes, and care actions from the field.</p>
        </div>

        <Chip icon="notebook" tone="forest" title={profile.statusDetail} ariaLabel={profile.statusDetail}>
          {profile.statusLabel}
        </Chip>
      </div>

      <div className="target-plant-history-list" aria-label="Plant history">
        {profile.history.map((entry) => (
          <PlantHistoryEntryCard key={`${selectedPlant.id}-${entry.title}`} entry={entry} />
        ))}
      </div>

      <article className="target-note-card target-plant-note-card">
        <span className="target-note-label">Trail note</span>
        <div className="target-note-body">
          <strong>Keep the thread short</strong>
          <span>Use photo notes and quick confirmations so the trail stays readable in the field.</span>
        </div>
        <div className="target-note-meta">{profile.noteMeta}</div>
      </article>
    </section>
  );
}

function PlantLifecycleView({
  profile,
  selectedPlant,
}: {
  profile: PlantProfile;
  selectedPlant: PlantInventoryRecord;
}) {
  const activeStage = profile.lifecycle.find((stage) => stage.active);

  return (
    <section className="target-plant-control-view">
      <div className="target-plant-control-head">
        <div className="target-plant-control-copy">
          <span className="section-label">Lifecycle</span>
          <h4>{selectedPlant.name}</h4>
          <p>From propagation to maintenance, all in one compact stage view.</p>
        </div>

        <Chip icon="layers" tone="amber" title={activeStage?.detail ?? profile.statusDetail} ariaLabel={activeStage?.detail ?? profile.statusDetail}>
          {activeStage?.label ?? profile.statusLabel}
        </Chip>
      </div>

      <div className="target-plant-lifecycle-grid" aria-label="Plant lifecycle stages">
        {profile.lifecycle.map((stage) => (
          <PlantLifecycleStageCard key={`${selectedPlant.id}-${stage.label}`} stage={stage} />
        ))}
      </div>

      <article className="target-note-card target-plant-note-card">
        <span className="target-note-label">Lifecycle note</span>
        <div className="target-note-body">
          <strong>Advance only when the stage is stable</strong>
          <span>{profile.noteBody}</span>
        </div>
        <div className="target-note-meta">{profile.noteMeta}</div>
      </article>
    </section>
  );
}

type PlantsPageMainProps = {
  serviceMeta: ReturnType<typeof getPlantsModel>["serviceMeta"];
  summaryStats: ReturnType<typeof getPlantsModel>["summaryStats"];
  inventoryFilters: ReturnType<typeof getPlantsModel>["inventoryFilters"];
  inventory: ReturnType<typeof getPlantsModel>["inventory"];
  profiles: ReturnType<typeof getPlantsModel>["profiles"];
  selectedPlantId: string;
  activeFilterId: PlantFilterId;
  onAddPlant: () => void;
  onFilterChange: (filterId: PlantFilterId) => void;
  onSelectPlant: (plantId: string) => void;
  onPlantAction: (message: string) => void;
  actionNotice: string | null;
};

function PlantsPageMain({
  serviceMeta,
  summaryStats,
  inventoryFilters,
  inventory,
  profiles,
  selectedPlantId,
  activeFilterId,
  onFilterChange,
  onSelectPlant,
  onPlantAction,
  actionNotice,
}: PlantsPageMainProps) {
  const visiblePlants = useMemo(() => {
    if (activeFilterId === "all") {
      return inventory;
    }

    return inventory.filter((plant) => plant.filters.includes(activeFilterId));
  }, [activeFilterId, inventory]);

  useEffect(() => {
    if (!visiblePlants.length) {
      return;
    }

    if (!visiblePlants.some((plant) => plant.id === selectedPlantId)) {
      onSelectPlant(visiblePlants[0].id);
    }
  }, [onSelectPlant, selectedPlantId, visiblePlants]);

  const selectedPlant = visiblePlants.find((plant) => plant.id === selectedPlantId) ?? visiblePlants[0] ?? inventory[0];
  const selectedProfile = selectedPlant ? profiles[selectedPlant.profileId] : undefined;

  if (!selectedPlant || !selectedProfile) {
    return null;
  }

  return (
    <section className="target-center-stack target-plants-main" aria-label="Plant inventory workspace">
      <article className="panel target-plants-panel">
        <div className="target-plants-head">
          <div className="target-plants-copy">
            <span className="section-label">Inventory operations</span>
            <h2>Plant inventory</h2>
          </div>

          <div className="target-plants-head-meta">
            <Chip
              icon="inventory"
              tone="forest"
              title={`${serviceMeta.name} ${serviceMeta.version}`}
              ariaLabel={`${serviceMeta.name} ${serviceMeta.version}`}
            >
              {serviceMeta.version}
            </Chip>
          </div>
        </div>

        <div className="target-plants-summary">
          {summaryStats.map((metric) => (
            <PlantSummaryCard key={metric.label} metric={metric} />
          ))}
        </div>

        {actionNotice ? (
          <article className="target-note-card target-plant-action-banner" aria-live="polite">
            <span className="target-note-label">Action queue</span>
            <div className="target-note-body">
              <strong>Frontend confirmation</strong>
              <span>{actionNotice}</span>
            </div>
            <div className="target-note-meta">Temporary UI feedback until the plant service is connected.</div>
          </article>
        ) : null}

        <div className="target-plants-workspace">
          <div className="target-plants-workspace-rail">
            <PlantSpotlightCard plant={selectedPlant} profile={selectedProfile} onPlantAction={onPlantAction} />
          </div>

          <div className="target-plant-workspace-stack">
            <div className="target-plant-toolbar">
              <div className="target-plant-filters" role="group" aria-label="Plant inventory filters">
                {inventoryFilters.map((filter) => {
                  const active = filter.id === activeFilterId;

                  return (
                    <button
                      key={filter.id}
                      className="target-plant-filter-button"
                      data-active={active ? "true" : "false"}
                      data-tone={filter.tone}
                      type="button"
                      aria-pressed={active}
                      onClick={() => onFilterChange(filter.id)}
                    >
                      <span className="target-plant-filter-icon">
                        <Icon name={filter.icon} />
                      </span>
                      <span className="target-plant-filter-copy">
                        <strong>{filter.label}</strong>
                        <span>{filter.count}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="target-plant-list-shell">
              <div className="target-plant-list" aria-label="Plant inventory rows">
                {visiblePlants.map((plant) => (
                  <PlantInventoryRow
                    key={plant.id}
                    plant={plant}
                    active={selectedPlant.id === plant.id}
                    onSelect={onSelectPlant}
                  />
                ))}
              </div>
            </div>

            <div className="target-plant-footer">
              <span>
                Showing {visiblePlants.length} of {inventory.length} plants
              </span>
              <button type="button" onClick={() => onFilterChange("all")}>
                View all
                <Icon name="chevron" />
              </button>
            </div>
          </div>
        </div>
      </article>
    </section>
  );
}

type PlantsControlPanelViewProps = {
  selectedPlant: PlantInventoryRecord;
  selectedProfile: PlantProfile;
  activeViewId: PlantViewId;
  onPlantAction: (message: string) => void;
};

function PlantsControlPanelView({ selectedPlant, selectedProfile, activeViewId, onPlantAction }: PlantsControlPanelViewProps) {
  const panel =
    activeViewId === "history" ? (
      <PlantHistoryView profile={selectedProfile} selectedPlant={selectedPlant} />
    ) : activeViewId === "lifecycle" ? (
      <PlantLifecycleView profile={selectedProfile} selectedPlant={selectedPlant} />
    ) : (
      <PlantCurrentView onPlantAction={onPlantAction} profile={selectedProfile} selectedPlant={selectedPlant} />
    );

  return (
    <>{panel}</>
  );
}

function PlantAddModal({
  open,
  onClose,
  onCreatePlant,
}: {
  open: boolean;
  onClose: () => void;
  onCreatePlant: (message: string) => void;
}) {
  useEffect(() => {
    if (!open) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="target-plant-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section className="target-plant-modal" role="dialog" aria-modal="true" aria-labelledby="add-plant-modal-title">
        <div className="target-plant-modal-head">
          <div className="target-plant-modal-copy">
            <span className="section-label">Add plant</span>
            <h3 id="add-plant-modal-title">New plant record</h3>
            <p>Capture the first photo, lock in the zone, and create a record that can carry care context from day one.</p>
          </div>

          <button className="target-plant-modal-close" type="button" aria-label="Close add plant dialog" onClick={onClose}>
            <Icon className="target-plant-modal-close-icon" name="minus" />
          </button>
        </div>

        <div className="target-plant-modal-layout">
          <div className="target-plant-modal-media">
            <PlantPhotoFrame
              actionLabel="Use camera"
              caption="Tap or drop in a field photo. Until then, the shell keeps the record visually grounded."
              eyebrow="Photo"
              title="Current photo"
              variant="hero"
              onAction={() => onCreatePlant("Camera capture ready for the new plant record.")}
            />
          </div>

          <form className="target-plant-modal-form">
            <div className="target-plant-modal-steps" aria-label="Add plant steps">
              <span>Identity</span>
              <span>Placement</span>
              <span>Photo</span>
              <span>First note</span>
            </div>

            <div className="target-plant-modal-grid">
              <label className="target-plant-field">
                <span>Common name</span>
                <input defaultValue="Japanese maple" placeholder="Plant name" type="text" />
              </label>
              <label className="target-plant-field">
                <span>Species</span>
                <input defaultValue="Acer palmatum" placeholder="Botanical name" type="text" />
              </label>
              <label className="target-plant-field">
                <span>Zone</span>
                <select defaultValue="gh1">
                  <option value="gh1">GH1 - North bench</option>
                  <option value="gh2">GH2 - Shade house</option>
                  <option value="gh3">GH3 - Container yard</option>
                  <option value="north-field">North field</option>
                </select>
              </label>
              <label className="target-plant-field">
                <span>Lifecycle stage</span>
                <select defaultValue="transplant">
                  <option value="propagation">Propagation</option>
                  <option value="transplant">Transplant</option>
                  <option value="establishment">Establishment</option>
                  <option value="maintenance">Maintenance</option>
                </select>
              </label>
            </div>

            <label className="target-plant-field target-plant-field-wide">
              <span>Initial note</span>
              <textarea
                defaultValue="Add a short record note, such as first scan details, placement, or a care instruction for the next route."
                rows={4}
              />
            </label>

            <div className="target-plant-modal-summary">
              <strong>Record preview</strong>
              <span>Plant inventory · Ready to assign · Photo pending</span>
            </div>

            <div className="target-plant-modal-actions">
              <button className="target-plant-modal-button" type="button" onClick={onClose}>
                Cancel
              </button>
              <button
                className="target-plant-modal-button"
                data-primary="true"
                type="button"
                onClick={() => {
                  onClose();
                  onCreatePlant("Created a plant draft for Japanese maple.");
                }}
              >
                Create plant
              </button>
            </div>
          </form>
        </div>
      </section>
    </div>
  );
}

export function PlantsPage(context: GardenServiceContext | null = null): PageWorkspaceView {
  const model = getPlantsModel(context);
  const [selectedPlantId, setSelectedPlantId] = useState(() => model.inventory.find((plant) => plant.selected)?.id ?? model.inventory[0]?.id ?? "");
  const [activeViewId, setActiveViewId] = useState<PlantViewId>("current");
  const [activeFilterId, setActiveFilterId] = useState<PlantFilterId>("all");
  const [addPlantOpen, setAddPlantOpen] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!actionNotice) {
      return;
    }

    const timeout = window.setTimeout(() => setActionNotice(null), 3600);

    return () => window.clearTimeout(timeout);
  }, [actionNotice]);

  const selectedPlant = useMemo(
    () => model.inventory.find((plant) => plant.id === selectedPlantId) ?? model.inventory[0],
    [model.inventory, selectedPlantId],
  );
  const selectedProfile = selectedPlant ? model.profiles[selectedPlant.profileId] : undefined;
  const controlButtons: DockTabItem[] = controlTabs.map((tab) => ({
    id: tab.id,
    label: tab.label,
    icon: tab.icon,
  }));

  return {
    main: (
      <PlantsPageMain
        activeFilterId={activeFilterId}
        actionNotice={actionNotice}
        onAddPlant={() => setAddPlantOpen(true)}
        inventory={model.inventory}
        inventoryFilters={model.inventoryFilters}
        onFilterChange={setActiveFilterId}
        onSelectPlant={setSelectedPlantId}
        onPlantAction={setActionNotice}
        profiles={model.profiles}
        selectedPlantId={selectedPlantId}
        serviceMeta={model.serviceMeta}
        summaryStats={model.summaryStats}
      />
    ),
    controlPanel: {
      eyebrow: "Plants",
      title: "Plant controls",
      headerAccessory: (
        <DockButtonGroup
          ariaLabel="Plant control panels"
          activeButtonId={activeViewId}
          onButtonChange={(tabId) => {
            if (tabId === "current" || tabId === "history" || tabId === "lifecycle") {
              setActiveViewId(tabId);
            }
          }}
          buttons={controlButtons}
        />
      ),
      content:
        selectedPlant && selectedProfile ? (
          <PlantsControlPanelView
            activeViewId={activeViewId}
            onPlantAction={setActionNotice}
            selectedPlant={selectedPlant}
            selectedProfile={selectedProfile}
          />
        ) : null,
    },
    overlay: <PlantAddModal open={addPlantOpen} onClose={() => setAddPlantOpen(false)} onCreatePlant={setActionNotice} />,
  };
}
