"""Command-line interface for offline analysis and explicit collection."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from http.client import HTTPException

from . import __version__
from .brightdata import HttpResponse, TransportError, collect, normalize_export, plan, resume, validate_live_manifest
from .core import MAX_PAYLOAD_BYTES, PROJECT, analyze
from .export import render_csv, render_json, render_markdown


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reviews-into-fixes", description="Create evidence-backed investigation candidates from reviews.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze_parser = sub.add_parser("analyze", help="analyze an offline JSON payload")
    analyze_parser.add_argument("input", type=Path)
    analyze_parser.add_argument("--out-dir", type=Path, required=True)
    analyze_parser.add_argument("--sources", type=Path)
    analyze_parser.add_argument("--dry-run", action="store_true")
    analyze_parser.add_argument("--overwrite", action="store_true")

    collect_parser = sub.add_parser("collect", help="plan or explicitly execute bounded collection")
    collect_parser.add_argument("manifest", type=Path)
    collect_parser.add_argument("--out", type=Path, required=True)
    collect_parser.add_argument("--live", action="store_true")
    collect_parser.add_argument("--accept-charges", action="store_true")
    collect_parser.add_argument("--approval", type=Path)
    collect_parser.add_argument("--dry-run", action="store_true")
    collect_parser.add_argument("--overwrite", action="store_true")

    import_parser = sub.add_parser("import-provider", help="normalize an authorized local provider export")
    import_parser.add_argument("file", type=Path)
    import_parser.add_argument("--kind", required=True, choices=["amazon_reviews", "google_maps_reviews", "web_page"])
    import_parser.add_argument("--role", required=True, choices=["review", "product_instructions"])
    import_parser.add_argument("--source-url", required=True)
    import_parser.add_argument("--observed-at", required=True)
    import_parser.add_argument("--source-prefix", default="import")
    import_parser.add_argument("--out", type=Path, required=True)
    import_parser.add_argument("--overwrite", action="store_true")

    resume_parser = sub.add_parser("resume", help="retrieve one explicitly approved pending snapshot")
    resume_parser.add_argument("receipt", type=Path)
    resume_parser.add_argument("--out", type=Path, required=True)
    resume_parser.add_argument("--live", action="store_true")
    resume_parser.add_argument("--accept-charges", action="store_true")
    resume_parser.add_argument("--approval", type=Path, required=True)
    resume_parser.add_argument("--overwrite", action="store_true")
    return parser


def _read_bytes(path: Path, *, max_bytes: int = MAX_PAYLOAD_BYTES) -> bytes:
    try:
        metadata = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise ValueError("input is not a readable regular file") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("input must be a regular file")
    if metadata.st_size > max_bytes:
        raise ValueError("input exceeds 2 MiB")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError("input must be a regular file") from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise ValueError("input must be a regular file")
        data = os.read(descriptor, max_bytes + 1)
    finally:
        os.close(descriptor)
    if len(data) > max_bytes:
        raise ValueError("input exceeds 2 MiB")
    return data


def _read_json(path: Path, *, max_bytes: int = MAX_PAYLOAD_BYTES):
    return json.loads(_read_bytes(path, max_bytes=max_bytes).decode("utf-8"))


def _system_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _validate_private_state_stat(metadata) -> None:
    if (not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700):
        raise ValueError("unsafe approval state directory")


def _open_state_home(state_home: Path) -> int:
    if not state_home.is_absolute():
        raise ValueError("unsafe approval state directory")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(os.path.sep, flags)
    try:
        for index, component in enumerate(state_home.parts[1:]):
            if not component:
                continue
            final = index == len(state_home.parts[1:]) - 1
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
                child = os.open(component, flags, dir_fd=descriptor)
            except OSError as exc:
                raise ValueError("unsafe approval state directory") from exc
            metadata = os.fstat(child)
            if not stat.S_ISDIR(metadata.st_mode):
                os.close(child)
                raise ValueError("unsafe approval state directory")
            if final:
                if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o022:
                    os.close(child)
                    raise ValueError("unsafe approval state directory")
            elif metadata.st_uid not in {0, os.getuid()} or (
                stat.S_IMODE(metadata.st_mode) & 0o022 and not stat.S_IMODE(metadata.st_mode) & stat.S_ISVTX
            ):
                os.close(child)
                raise ValueError("unsafe approval state directory")
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _open_private_child(parent_fd: int, name: str) -> int:
    try:
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        _validate_private_state_stat(metadata)
        child = os.open(name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                        dir_fd=parent_fd)
        opened = os.fstat(child)
        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            os.close(child)
            raise ValueError("unsafe approval state directory")
        _validate_private_state_stat(opened)
        return child
    except (OSError, ValueError) as exc:
        raise ValueError("unsafe approval state directory") from exc


def _approval_state_consumer(identity: dict, *, state_home: Path | None = None) -> None:
    approval_id, nonce, approval_digest = (identity.get("approval_id"), identity.get("nonce"),
                                             identity.get("approval_sha256"))
    if (not isinstance(approval_id, str) or not isinstance(nonce, str) or not isinstance(approval_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", nonce)
            or not re.fullmatch(r"[0-9a-f]{64}", approval_digest)):
        raise ValueError("invalid approval identity")
    base = state_home or Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".reviews-into-fixes-state")))
    base_fd = _open_state_home(base)
    try:
        app_fd = _open_private_child(base_fd, "reviews-into-fixes")
    finally:
        os.close(base_fd)
    try:
        consumption_fd = _open_private_child(app_fd, "approval-consumption")
    finally:
        os.close(app_fd)
    try:
        marker_name = hashlib.sha256(
            f"{approval_id}\x00{nonce}".encode("utf-8")
        ).hexdigest()
        payload = json.dumps({"approval_id": approval_id,
                              "nonce_sha256": hashlib.sha256(nonce.encode()).hexdigest(),
                              "approval_sha256": approval_digest},
                             sort_keys=True, separators=(",", ":")).encode()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            marker_fd = os.open(marker_name, flags, 0o600, dir_fd=consumption_fd)
        except FileExistsError as exc:
            try:
                marker_fd = os.open(marker_name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=consumption_fd)
            except OSError as marker_error:
                raise ValueError("unsafe approval state marker") from marker_error
            try:
                metadata = os.fstat(marker_fd)
                actual = os.read(marker_fd, 2048)
                if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                        or stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_nlink != 1
                        or actual != payload):
                    raise ValueError("unsafe approval state marker") from exc
            finally:
                os.close(marker_fd)
            raise ValueError("approval already consumed") from exc
        try:
            view = memoryview(payload)
            while view:
                view = view[os.write(marker_fd, view):]
            os.fsync(marker_fd)
        finally:
            os.close(marker_fd)
        os.fsync(consumption_fd)
    finally:
        os.close(consumption_fd)


def _atomic_write(path: Path, content: str, overwrite: bool) -> None:
    _validate_output_path(path, overwrite)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _validate_output_path(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ValueError("output already exists")
    if not path.parent.is_dir():
        raise ValueError("output parent directory does not exist")


def _write_many(outputs: dict[Path, str], overwrite: bool) -> None:
    collisions = [path.name for path in outputs if path.exists() and not overwrite]
    if collisions:
        raise ValueError("outputs already exist: " + ", ".join(collisions))
    for path in outputs:
        if not path.parent.is_dir():
            raise ValueError("output directory does not exist")
    prepared: dict[Path, str] = {}
    backups: dict[Path, str] = {}
    committed: list[Path] = []
    try:
        for path, content in outputs.items():
            descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=path.parent)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            prepared[path] = temporary
            if path.exists():
                backup_descriptor, backup = tempfile.mkstemp(prefix=f".{path.name}.backup-", dir=path.parent)
                with os.fdopen(backup_descriptor, "wb") as handle:
                    handle.write(path.read_bytes())
                    handle.flush()
                    os.fsync(handle.fileno())
                backups[path] = backup
        for path in outputs:
            os.replace(prepared[path], path)
            prepared.pop(path)
            committed.append(path)
    except Exception:
        for path in reversed(committed):
            if path in backups:
                os.replace(backups.pop(path), path)
            else:
                path.unlink(missing_ok=True)
        raise
    finally:
        for temporary in [*prepared.values(), *backups.values()]:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _transport(request):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    raw = urllib.request.Request(request.url, data=request.body or None, headers=request.headers, method=request.method)
    try:
        try:
            with opener.open(raw, timeout=request.timeout_seconds) as response:
                body = response.read(2 * 1024 * 1024 + 1)
                return HttpResponse(response.status, dict(response.headers), body)
        except urllib.error.HTTPError as exc:
            with exc:
                return HttpResponse(exc.code, dict(exc.headers), exc.read(2 * 1024 * 1024 + 1))
    except urllib.error.URLError as exc:
        code = "completion_unknown" if isinstance(exc.reason, TimeoutError) else "transport_error"
        raise TransportError(code) from exc
    except TimeoutError as exc:
        raise TransportError("completion_unknown") from exc
    except (OSError, HTTPException) as exc:
        raise TransportError("transport_error") from exc


def _error(code: str, message: str, requests_made: int = 0, **details) -> None:
    output = {"code": code, "message": message, "requests_made": requests_made, **details}
    print(json.dumps(output, sort_keys=True), file=sys.stderr)


def _private_recovery_dir() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    base = Path(configured) if configured else Path.home() / ".local" / "state"
    if not base.is_absolute():
        base = Path.home() / ".local" / "state"
    fallback = Path(tempfile.gettempdir()) / f"reviews-into-fixes-{os.getuid()}"
    last_error = None
    for candidate in dict.fromkeys((base, fallback)):
        try:
            candidate.mkdir(parents=True, exist_ok=True, mode=0o700)
            metadata = os.stat(candidate, follow_symlinks=False)
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise OSError("state directory is not owned by the current user")
            app_state = candidate / "reviews-into-fixes"
            app_state.mkdir(exist_ok=True, mode=0o700)
            metadata = os.stat(app_state, follow_symlinks=False)
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise OSError("recovery directory is not owned by the current user")
            os.chmod(app_state, 0o700)
            recovery = app_state / "recovery"
            recovery.mkdir(exist_ok=True, mode=0o700)
            metadata = os.stat(recovery, follow_symlinks=False)
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise OSError("recovery directory is not owned by the current user")
            os.chmod(recovery, 0o700)
            return recovery
        except OSError as exc:
            last_error = exc
    raise OSError("no private recovery directory is writable") from last_error


def _write_recovery_library(library: dict) -> tuple[str, Path]:
    original = json.dumps(library, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    recovery_id = hashlib.sha256(original).hexdigest()
    recovered = {**library, "recovery_id": recovery_id}
    content = (json.dumps(recovered, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    directory = _private_recovery_dir()
    path = directory / f"collection-{recovery_id}.library.json"
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=directory)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            if _read_bytes(path, max_bytes=MAX_PAYLOAD_BYTES) != content:
                raise OSError("recovery ID collision")
        directory_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return recovery_id, path


def _persist_after_output_failure(library: dict, *, requests_this_run: int | None = None) -> None:
    receipt = library.get("receipt", {})
    requests_made = receipt.get("requests_made", 0)
    if isinstance(requests_made, bool) or not isinstance(requests_made, int) or requests_made < 0:
        requests_made = 0
    sources = library.get("sources", [])
    jobs = receipt.get("jobs", [])
    source_ids = [source["id"] for source in sources if isinstance(source, dict) and isinstance(source.get("id"), str)]
    job_ids = [job["id"] for job in jobs if isinstance(job, dict) and isinstance(job.get("id"), str)]
    details = {"requests_this_run": requests_this_run} if requests_this_run is not None else {}
    try:
        recovery_id, recovery_path = _write_recovery_library(library)
    except (OSError, ValueError):
        _error("output_persist_failed", "Collection was attempted; target and recovery writes failed. Do not retry automatically.",
               requests_made, recovery_saved=False, recovery_path=None, source_ids=source_ids, job_ids=job_ids, **details)
        return
    _error("output_persist_failed", "Output write failed after collection; recover the saved library and do not retry.",
           requests_made, recovery_saved=True, recovery_path=str(recovery_path), receipt_id=recovery_id,
           source_ids=source_ids, job_ids=job_ids, **details)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "analyze":
            payload = _read_json(args.input)
            if args.sources:
                library = _read_json(args.sources)
                if library.get("project") != PROJECT or not isinstance(library.get("sources"), list):
                    raise ValueError("invalid collection library")
                existing = {source.get("id") for source in payload.get("sources", [])}
                incoming = {source.get("id") for source in library["sources"]}
                if len(incoming) != len(library["sources"]) or existing & incoming:
                    raise ValueError("duplicate source IDs in appended library")
                payload = {**payload, "sources": payload.get("sources", []) + library["sources"]}
            report = analyze(payload)
            if args.dry_run:
                print(json.dumps({"project": PROJECT, "source_count": len(payload["sources"]),
                                  "card_count": len(report["cards"]), "requests_made": 0}, sort_keys=True))
                return 0
            args.out_dir.mkdir(parents=True, exist_ok=True)
            _write_many({args.out_dir / "report.json": render_json(report), args.out_dir / "fixes.md": render_markdown(report),
                         args.out_dir / "fixes.csv": render_csv(report)}, args.overwrite)
            print(json.dumps({"status": report["status"], "decision": report["decision"],
                              "card_count": len(report["cards"]), "requests_made": 0,
                              "out_dir": str(args.out_dir)}, sort_keys=True))
            return 0

        if args.command == "import-provider":
            _validate_output_path(args.out, args.overwrite)
            records = _read_bytes(args.file).decode("utf-8") if args.kind == "web_page" else _read_json(args.file)
            library = normalize_export(args.kind, records, role=args.role, source_url=args.source_url,
                                       observed_at=args.observed_at, source_prefix=args.source_prefix)
            _atomic_write(args.out, json.dumps(library, ensure_ascii=False, indent=2, sort_keys=True) + "\n", args.overwrite)
            print(json.dumps({"status": library["receipt"]["status"], "retained_records": len(library["sources"]),
                              "requests_made": 0, "out": str(args.out)}, sort_keys=True))
            return 4 if library["receipt"]["status"] == "processed_with_exclusions" else 0

        if args.command == "collect":
            manifest = _read_json(args.manifest)
            planned = validate_live_manifest(manifest) if args.live else plan(manifest)
            if args.dry_run:
                print(json.dumps(planned, sort_keys=True))
                return 0
            _validate_output_path(args.out, args.overwrite)
            if not args.live:
                raise ValueError("collection requires --live; use --dry-run to plan without network")
            if not args.accept_charges or not args.approval:
                raise ValueError("live collection requires --accept-charges and --approval")
            approval = _read_json(args.approval)
            api_key = os.environ.get("BRIGHT_DATA_API_KEY", "")
            zones = {"web_unlocker": os.environ.get("BRIGHT_DATA_WEB_UNLOCKER_ZONE", ""),
                     "serp": os.environ.get("BRIGHT_DATA_SERP_ZONE", "")}
            now = _system_now()
            library = collect(manifest, approval=approval, api_key=api_key, zones=zones, transport=_transport, now=now,
                              approval_consumer=_approval_state_consumer)
            try:
                _atomic_write(args.out, json.dumps(library, ensure_ascii=False, indent=2, sort_keys=True) + "\n", args.overwrite)
            except (OSError, ValueError):
                _persist_after_output_failure(library)
                return 2
            print(json.dumps({"status": library["receipt"]["status"], "requests_made": library["receipt"]["requests_made"],
                              "out": str(args.out)}, sort_keys=True))
            return 4 if library["receipt"]["status"] in {"processed_with_exclusions", "pending", "completion_unknown"} else 3 if library["receipt"]["status"] == "transport_failed" else 0

        if not args.live or not args.accept_charges:
            raise ValueError("resume requires --live and --accept-charges")
        _validate_output_path(args.out, args.overwrite)
        collection = _read_json(args.receipt)
        if (not isinstance(collection, dict) or collection.get("schema_version") != "1.0"
                or collection.get("project") != PROJECT or collection.get("transport_contract_version") != "1.0"
                or not isinstance(collection.get("sources"), list) or not isinstance(collection.get("receipt"), dict)
                or collection["receipt"].get("retained_records") != len(collection["sources"])):
            raise ValueError("invalid collection library")
        approval = _read_json(args.approval)
        api_key = os.environ.get("BRIGHT_DATA_API_KEY", "")
        now = _system_now()
        resume_error = None
        try:
            resumed = resume(collection["receipt"], approval=approval, api_key=api_key, transport=_transport, now=now,
                             approval_consumer=_approval_state_consumer)
        except TransportError as exc:
            if exc.receipt is None:
                raise
            resume_error = exc
            resumed = {"sources": [], "receipt": exc.receipt}
        library = {**collection, "sources": collection["sources"] + resumed["sources"],
                   "receipt": resumed["receipt"]}
        requests_this_run = library["receipt"]["requests_made"] - collection["receipt"]["requests_made"]
        try:
            _atomic_write(args.out, json.dumps(library, ensure_ascii=False, indent=2, sort_keys=True) + "\n", args.overwrite)
        except (OSError, ValueError):
            _persist_after_output_failure(library, requests_this_run=requests_this_run)
            return 2
        if resume_error is not None:
            _error(resume_error.code, "Snapshot download failed; the library was saved. No retry was made.",
                   library["receipt"]["requests_made"], requests_this_run=requests_this_run, recovery_saved=True,
                   recovery_path=str(args.out.absolute()), source_ids=[source["id"] for source in library["sources"]],
                   job_ids=[job["id"] for job in library["receipt"]["jobs"]])
            return 4 if library["receipt"]["status"] == "completion_unknown" else 3
        return 4 if library["receipt"]["status"] in {"pending", "processed_with_exclusions", "completion_unknown"} else 0
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        detail = str(exc).casefold()
        message = "live target is not allowed" if any(term in detail for term in ("live target", "fixture host", "reserved/private")) else "invalid input or configuration"
        _error("invalid_input", message)
        return 2
    except TransportError as exc:
        _error(exc.code, "Collection failed safely.")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
