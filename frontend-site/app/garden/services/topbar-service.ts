export type GardenTopbarModel = {
  weather: {
    icon: "weather";
    value: string;
    detail: string;
    meta: string[];
  };
};

export function getTopbarModel(): GardenTopbarModel {
  return {
    weather: {
      icon: "weather",
      value: "72°F",
      detail: "Partly Cloudy",
      meta: ["H 74°", "L 56°", "18% rain"],
    },
  };
}
