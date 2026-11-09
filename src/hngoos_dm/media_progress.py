"""Count selected media streams without confusing one stream with the whole job."""


class MediaProgress:
    def __init__(self, callback):
        self.callback = callback
        self.streams = {}

    def _stream(self, info):
        key = (str(info.get("id") or ""), str(info.get("format_id") or ""))
        return self.streams.setdefault(key, {"downloaded": 0, "total": 0, "estimated": False, "finished": False})

    def plan(self, info):
        for item in info.get("requested_formats") or [info]:
            stream = self._stream(dict(item, id=info.get("id")))
            exact = item.get("filesize")
            estimate = item.get("filesize_approx")
            if not exact and not estimate and item.get("tbr") and info.get("duration"):
                estimate = item["tbr"]*1000/8*info["duration"]
            if exact or estimate:
                stream.update(total=int(exact or estimate), estimated=not bool(exact))

    def __call__(self, data):
        if "downloaded_bytes" not in data:
            # Postprocessor hooks also say "finished", without byte counters.
            if self.callback and "postprocessor" not in data:
                self.callback(data)
            return
        info = data.get("info_dict") or {}
        stream = self._stream(info)
        downloaded = int(data.get("downloaded_bytes") or 0)
        exact = data.get("total_bytes") or info.get("filesize")
        estimate = data.get("total_bytes_estimate") or info.get("filesize_approx")
        finished = data.get("status") == "finished"
        if finished:
            exact = downloaded
        if exact:
            stream.update(total=int(exact), estimated=False)
        elif estimate and (not stream["total"] or stream["estimated"]):
            stream.update(total=int(estimate), estimated=True)
        stream.update(downloaded=downloaded, finished=finished)
        streams = list(self.streams.values())
        total = sum(item["total"] for item in streams) if all(item["total"] for item in streams) else 0
        received = sum(item["downloaded"] for item in streams)
        estimated = any(item["estimated"] for item in streams)
        if total and received > total:
            total, estimated = received, True
        if self.callback:
            self.callback(dict(data, downloaded_bytes=received, total_bytes=total,
                               total_estimated=estimated,
                               status="finished" if all(item["finished"] for item in streams) else "downloading"))
