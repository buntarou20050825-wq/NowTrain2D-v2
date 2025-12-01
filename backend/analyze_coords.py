import json
import math

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def dist(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def main():
    stations = load_json('../data/mini-tokyo-3d/stations.json')
    railways = load_json('../data/mini-tokyo-3d/railways.json')
    coords_data = load_json('../data/mini-tokyo-3d/coordinates.json')

    yamanote_id = "JR-East.Yamanote"
    
    # Get Yamanote stations
    yamanote_line = next(r for r in railways if r['id'] == yamanote_id)
    yamanote_station_ids = yamanote_line['stations']
    y_stations = [s for s in stations if s['id'] in yamanote_station_ids]
    
    # Get Yamanote track coords
    y_coords_entry = next(c for c in coords_data['railways'] if c['id'] == yamanote_id)
    
    # Flatten coords (assuming simple loop for now, though App.jsx handles sublines)
    all_track_points = []
    for sub in y_coords_entry['sublines']:
        all_track_points.extend(sub['coords'])

    with open('analyze_output.txt', 'w', encoding='utf-8') as f:
        f.write(f"Total track points: {len(all_track_points)}\n")
        f.write(f"Total stations: {len(y_stations)}\n")

        # Check matching
        for st in y_stations:
            st_coord = st['coord']
            # Find closest track point
            min_d = float('inf')
            closest_idx = -1
            
            for i, p in enumerate(all_track_points):
                d = dist(st_coord, p)
                if d < min_d:
                    min_d = d
                    closest_idx = i
            
            f.write(f"Station {st['title']['ja']} ({st['id']}): Closest index {closest_idx}, Dist {min_d:.6f}\n")
            if min_d > 0.0001: # Approx 10 meters?
                f.write(f"  WARNING: Station far from track!\n")

if __name__ == "__main__":
    main()
