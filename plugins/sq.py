import copy
import os

import audio

def generate_json_from_data(params, read_data_callback, raw_charts):
    def combine_metadata_with_chart(metadata, chart):
        if not metadata:
            return chart

        chart_combined = copy.deepcopy(chart)

        for event in metadata['beat_data']:
            if event['name'] in ['measure', 'beat']:
                chart_combined['beat_data'].append(event)

        return chart_combined


    def combine_guitar_charts(guitar_charts, bass_charts):
        # Combine guitar and bass charts
        parsed_bass_charts = []

        for chart in guitar_charts:
            # Find equivalent chart
            for chart2 in bass_charts:
                if chart['header']['difficulty'] != chart2['header']['difficulty']:
                    continue

                if 'level' in chart2['header']:
                    if 'level' not in chart['header']:
                        chart['header']['level'] = {}

                    for k in chart2['header']['level']:
                        chart['header']['level'][k] = chart2['header']['level'][k]

                    for event in chart2['timestamp'][timestamp_key]:
                        if event['name'] != "note":
                            continue

                        if timestamp_key not in chart['timestamp']:
                            chart['timestamp'][timestamp_key] = []

                        chart['timestamp'][timestamp_key].append(event)

                parsed_bass_charts.append(chart2)

        for chart in parsed_bass_charts:
            bass_charts.remove(chart)

        return guitar_charts, bass_charts


    def split_charts_by_parts(charts):
        guitar_charts = []
        bass_charts = []
        open_charts = []
        guitar1_charts = []
        guitar2_charts = []

        for chart in charts:
            if chart['header']['is_metadata'] != 0:
                continue

            game_type = ["drum", "guitar", "bass", "open", "guitar1", "guitar2"][chart['header']['game_type']]
            if game_type == "guitar":
                guitar_charts.append(chart)
            elif game_type == "bass":
                bass_charts.append(chart)
            elif game_type == "open":
                open_charts.append(chart)
            elif game_type == "guitar1":
                guitar1_charts.append(chart)
            elif game_type == "guitar2":
                guitar2_charts.append(chart)

        # Remove charts from chart list
        for chart in guitar_charts:
            charts.remove(chart)

        for chart in bass_charts:
            charts.remove(chart)

        for chart in open_charts:
            charts.remove(chart)

        for chart in guitar1_charts:
            charts.remove(chart)

        for chart in guitar2_charts:
            charts.remove(chart)

        return charts, guitar_charts, bass_charts, open_charts, guitar1_charts, guitar2_charts


    def add_note_durations(chart, params):
        def get_duration_from_file(sound_metadata, entry):
            if 'duration' in entry and entry['duration'] != 0 and entry['duration'] != 0.0:
                return entry['duration']

            filename = entry['filename']

            if 'NoFilename' in entry['flags']:
                filename = "%04x.wav" % entry['sound_id']

            return audio.get_duration(os.path.join(params['sound_folder'], filename))

        sound_metadata = params.get('sound_metadata', [])
        duration_lookup = {}

        if not sound_metadata or 'entries' not in sound_metadata:
            return chart

        for entry in sound_metadata['entries']:
            duration_lookup[entry['sound_id']] = get_duration_from_file(sound_metadata, entry)

        for event in chart['beat_data']:
            if event['name'] in ['note', 'auto'] and 'note_length' not in event['data']:
                x = duration_lookup.get(event['data']['sound_id'], 0) * 300
                event['data']['note_length'] = int(round(x))

        return chart


    def remove_extra_beats(chart):
        new_beat_data = []
        found_measures = []

        for x in sorted(chart['beat_data'], key=lambda x: int(x['timestamp'])):
            if x['name'] == "measure":
                found_measures.append(x['timestamp'])

        discarded_beats = []
        for x in sorted(chart['beat_data'], key=lambda x: int(x['timestamp'])):
            if x['name'] == "beat" and x['timestamp'] in found_measures:
                discarded_beats.append(x['timestamp'])
                continue

            new_beat_data.append(x)

        for idx, x in enumerate(new_beat_data):
            if x['name'] == "measure" and x['timestamp'] in discarded_beats:
                new_beat_data[idx]['merged_beat'] = True

        chart['beat_data'] = new_beat_data

        return chart

    combine_guitars = params['merge_guitars'] if 'merge_guitars' in params else False
    events = params['events'] if 'events' in params else {}

    charts = []
    for chart_info in raw_charts:
        chart, game_type, difficulty, is_metadata = chart_info

        other_params = {
            'difficulty': difficulty,
            'is_metadata': is_metadata,
            'game_type': game_type,
        }

        parsed_chart = read_data_callback(chart, events, other_params)

        if not parsed_chart:
            continue

        parsed_chart = remove_extra_beats(parsed_chart)

        game_type = ["drum", "guitar", "bass", "open", "guitar1", "guitar2"][parsed_chart['header']['game_type']]
        if game_type in ["guitar", "bass", "open"]:
            parsed_chart = add_note_durations(parsed_chart, params)

        charts.append(parsed_chart)
        charts[-1]['header']['musicid'] = params['musicid']

    metadata_chart = None
    for chart in charts:
        if chart['header']['is_metadata'] == 1:
            metadata_chart = chart
            break

    for chart_idx, chart in enumerate(charts):
        if chart['header']['is_metadata'] == 1:
            continue

        charts[chart_idx] = combine_metadata_with_chart(metadata_chart, chart)

    if metadata_chart:
        charts.remove(metadata_chart)

    charts, guitar_charts, bass_charts, open_charts, guitar1_charts, guitar2_charts = split_charts_by_parts(charts)

    if combine_guitars:
        guitar_charts, bass_charts = combine_guitar_charts(guitar_charts, bass_charts)
        guitar1_charts, guitar2_charts = combine_guitar_charts(guitar1_charts, guitar2_charts)

    # Merge all charts back together after filtering, merging guitars etc
    charts += guitar_charts
    charts += bass_charts
    charts += open_charts
    charts += guitar1_charts
    charts += guitar2_charts

    output_data = {
        'charts': charts
    }

    return output_data


def get_class():
    return None
