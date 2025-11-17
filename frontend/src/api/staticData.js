const BASE_PATH = "/data/mini-tokyo-3d";

async function fetchJson(path) {
  try {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`Failed to fetch ${path}`);
    return await res.json();
  } catch (error) {
    console.error(`Error fetching ${path}:`, error);
    // TODO: 将来的にはここで
    // - 再試行（リトライ）
    // - 画面上へのエラー表示（トースト/ダイアログなど）
    // を行う。MS1ではログ出力にとどめる。
    return null; // もしくは [] を返してもよいが、呼び出し側で null チェックを行うこと
  }
}

export function fetchRailways() {
  return fetchJson(`${BASE_PATH}/railways.json`);
}

export function fetchStations() {
  return fetchJson(`${BASE_PATH}/stations.json`);
}

export function fetchCoordinates() {
  return fetchJson(`${BASE_PATH}/coordinates.json`);
}
