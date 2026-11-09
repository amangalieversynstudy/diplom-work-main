import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Check, Crown, Gift, LogOut, Repeat, Shield, Swords, Timer, UserPlus, Users, X } from "lucide-react";
import Layout from "../components/Layout";
import Button from "../components/Button";
import EmptyScroll, { SkeletonScroll } from "../components/EmptyScroll";
import { Profile, Social } from "../lib/api";
import { errorBody, serverMessage } from "../lib/apiErrors";
import { useI18n } from "../lib/i18n";
import { canTeach } from "../lib/roles";
import { sanitizeHtml } from "../lib/sanitize";
import { storyToHtml } from "../lib/story";

// Таверна: друзья, обмен предметами, гильдии и дуэли-квизы. Правила живут на сервере (backend/social):
// здесь только показ, формы и понятные сообщения об отказах.
const TABS = [
  { id: "friends", icon: Users, badge: "friends" },
  { id: "trade", icon: Repeat, badge: "trades" },
  { id: "guilds", icon: Shield },
  { id: "arena", icon: Swords, badge: "duels" },
];
const ITEMS = ["hint_scrolls", "skeleton_scrolls"];
const EMBLEMS = { dragon: "🐉", owl: "🦉", wolf: "🐺", phoenix: "🔥", tower: "🏰", serpent: "🐍" };
const QTY = [1, 2, 3, 4, 5];

const panel = "rounded-2xl border border-border bg-panel p-4 md:p-5";
const field = "w-full rounded-xl border border-border bg-surface px-3 py-2 text-text outline-none focus:border-primary";
const sectionTitle = "mb-3 font-title text-xl text-text";

function useErrorText(t) {
  return useCallback(
    (error) => {
      const code = errorBody(error)?.code;
      const key = `tavern.errors.${code}`;
      const local = code ? t(key) : null;
      if (local && local !== key) return local;
      return serverMessage(error, t("tavern.errors.generic"), t("tavern.errors.offline"));
    },
    [t]
  );
}

function fill(template, values) {
  return Object.entries(values).reduce((text, [key, value]) => text.replace(`{${key}}`, value), template || "");
}

function PlayerLine({ card, t }) {
  return (
    <div className="min-w-0">
      <p className="truncate font-title text-lg text-text">{card.username}</p>
      <p className="text-xs text-muted">
        {t("tavern.level")} {card.level ?? 1}
        {card.xp != null ? ` · ${card.xp} XP` : ""}
      </p>
    </div>
  );
}

// ── друзья ──────────────────────────────────────────────────────────────────

function FriendsTab({ t, data, setData, errorText, onChanged, goTo }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(null);
  const [confirming, setConfirming] = useState(null);

  const act = async (key, call, success) => {
    setBusy(key);
    try {
      const next = await call();
      setData(next);
      if (success) toast.success(typeof success === "function" ? success(next) : success);
      onChanged();
      return true;
    } catch (error) {
      toast.error(errorText(error));
      return false;
    } finally {
      setBusy(null);
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!name.trim()) return;
    const done = await act("add", () => Social.addFriend(name.trim()), (next) =>
      next.status === "accepted" ? t("tavern.friends.nowFriends") : t("tavern.friends.sent")
    );
    if (done) setName("");
  };

  const remove = (id) => {
    if (confirming !== id) {
      setConfirming(id);
      setTimeout(() => setConfirming((current) => (current === id ? null : current)), 4000);
      return;
    }
    setConfirming(null);
    act(`rm-${id}`, () => Social.removeFriend(id), t("tavern.friends.removed"));
  };

  if (!data) return <SkeletonScroll label={t("tavern.loading")} />;

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className={`${panel} flex flex-col gap-3 sm:flex-row sm:items-end`}>
        <label className="flex-1">
          <span className="mb-1 block text-sm font-medium text-muted">{t("tavern.friends.addLabel")}</span>
          <input
            className={field}
            value={name}
            maxLength={150}
            autoComplete="off"
            placeholder={t("tavern.friends.addPlaceholder")}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <Button type="submit" icon={UserPlus} loading={busy === "add"} disabled={!name.trim()}>
          {t("tavern.friends.add")}
        </Button>
      </form>

      {data.incoming.length > 0 && (
        <section>
          <h2 className={sectionTitle}>{t("tavern.friends.incoming")}</h2>
          <ul className="space-y-2">
            {data.incoming.map((card) => (
              <li key={card.id} className={`${panel} flex flex-wrap items-center justify-between gap-3`}>
                <PlayerLine card={card} t={t} />
                <div className="flex gap-2">
                  <Button size="sm" icon={Check} loading={busy === `ok-${card.id}`}
                    onClick={() => act(`ok-${card.id}`, () => Social.acceptFriend(card.id), t("tavern.friends.nowFriends"))}>
                    {t("tavern.friends.accept")}
                  </Button>
                  <Button size="sm" variant="outline" icon={X} loading={busy === `rm-${card.id}`}
                    onClick={() => act(`rm-${card.id}`, () => Social.removeFriend(card.id))}>
                    {t("tavern.friends.decline")}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2 className={sectionTitle}>{t("tavern.friends.list")}</h2>
        {data.friends.length === 0 ? (
          <EmptyScroll icon={Users}>{t("tavern.friends.empty")}</EmptyScroll>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2">
            {data.friends.map((card) => (
              <li key={card.id} className={`${panel} flex flex-col gap-3`}>
                <PlayerLine card={card} t={t} />
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="secondary" icon={Gift} onClick={() => goTo("trade", card.username)}>
                    {t("tavern.friends.trade")}
                  </Button>
                  <Button size="sm" variant="secondary" icon={Swords} onClick={() => goTo("arena", card.username)}>
                    {t("tavern.friends.duel")}
                  </Button>
                  <Button size="sm" variant="ghost" loading={busy === `rm-${card.id}`} onClick={() => remove(card.id)}>
                    {confirming === card.id ? t("tavern.friends.removeConfirm") : t("tavern.friends.remove")}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {data.outgoing.length > 0 && (
        <section>
          <h2 className={sectionTitle}>{t("tavern.friends.outgoing")}</h2>
          <ul className="space-y-2">
            {data.outgoing.map((card) => (
              <li key={card.id} className={`${panel} flex flex-wrap items-center justify-between gap-3`}>
                <PlayerLine card={card} t={t} />
                <Button size="sm" variant="outline" loading={busy === `rm-${card.id}`}
                  onClick={() => act(`rm-${card.id}`, () => Social.removeFriend(card.id))}>
                  {t("tavern.friends.cancel")}
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

// ── обмен ───────────────────────────────────────────────────────────────────

function itemText(t, item, qty) {
  return `${qty} × ${t(`tavern.items.${item}`)}`;
}

function TradeTab({ t, friends, errorText, onChanged, prefill }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(null);
  const [form, setForm] = useState({ to: prefill || "", give_item: ITEMS[0], give_qty: 1, swap: false, ask_item: ITEMS[1], ask_qty: 1 });

  const load = useCallback(() => Social.trades().then(setData).catch((error) => toast.error(errorText(error))), [errorText]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (prefill) setForm((current) => ({ ...current, to: prefill }));
  }, [prefill]);

  const act = async (key, call, success) => {
    setBusy(key);
    try {
      setData(await call());
      if (success) toast.success(success);
      onChanged();
    } catch (error) {
      toast.error(errorText(error));
      load();
    } finally {
      setBusy(null);
    }
  };

  const submit = (event) => {
    event.preventDefault();
    const payload = { to: form.to, give_item: form.give_item, give_qty: Number(form.give_qty) };
    if (form.swap) Object.assign(payload, { ask_item: form.ask_item, ask_qty: Number(form.ask_qty) });
    act("offer", () => Social.offerTrade(payload), t("tavern.trade.sent"));
  };

  if (!data) return <SkeletonScroll label={t("tavern.loading")} />;
  const friendList = friends?.friends || [];

  const offerText = (trade) => {
    const give = itemText(t, trade.give_item, trade.give_qty);
    const back = trade.ask_qty ? `${t("tavern.trade.for")} ${itemText(t, trade.ask_item, trade.ask_qty)}` : t("tavern.trade.gift");
    return `${give} ${back}`;
  };

  return (
    <div className="space-y-6">
      <section className={panel}>
        <h2 className={sectionTitle}>{t("tavern.trade.inventory")}</h2>
        <div className="flex flex-wrap gap-2">
          {ITEMS.map((item) => (
            <span key={item} className="rounded-full border border-border bg-surface px-3 py-1 text-sm text-text">
              {t(`tavern.items.${item}`)}: <b>{data.inventory?.[item] ?? 0}</b>
            </span>
          ))}
        </div>
        <p className="mt-3 text-xs text-muted">{t("tavern.trade.aiNote")}</p>
      </section>

      {friendList.length === 0 ? (
        <EmptyScroll icon={Repeat}>{t("tavern.trade.noFriends")}</EmptyScroll>
      ) : (
        <form onSubmit={submit} className={`${panel} space-y-4`}>
          <h2 className={sectionTitle}>{t("tavern.trade.offerTitle")}</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <label>
              <span className="mb-1 block text-sm font-medium text-muted">{t("tavern.trade.to")}</span>
              <select className={field} value={form.to} onChange={(e) => setForm({ ...form, to: e.target.value })} required>
                <option value="">{t("tavern.trade.choose")}</option>
                {friendList.map((card) => (
                  <option key={card.id} value={card.username}>{card.username}</option>
                ))}
              </select>
            </label>
            <label>
              <span className="mb-1 block text-sm font-medium text-muted">{t("tavern.trade.give")}</span>
              <select className={field} value={form.give_item} onChange={(e) => setForm({ ...form, give_item: e.target.value })}>
                {ITEMS.map((item) => <option key={item} value={item}>{t(`tavern.items.${item}`)}</option>)}
              </select>
            </label>
            <label>
              <span className="mb-1 block text-sm font-medium text-muted">{t("tavern.trade.qty")}</span>
              <select className={field} value={form.give_qty} onChange={(e) => setForm({ ...form, give_qty: e.target.value })}>
                {QTY.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm text-text">
            <input type="checkbox" className="h-5 w-5 accent-[var(--primary)]" checked={form.swap}
              onChange={(e) => setForm({ ...form, swap: e.target.checked })} />
            {t("tavern.trade.swap")}
          </label>
          {form.swap && (
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="sm:col-start-2">
                <span className="mb-1 block text-sm font-medium text-muted">{t("tavern.trade.ask")}</span>
                <select className={field} value={form.ask_item} onChange={(e) => setForm({ ...form, ask_item: e.target.value })}>
                  {ITEMS.map((item) => <option key={item} value={item}>{t(`tavern.items.${item}`)}</option>)}
                </select>
              </label>
              <label>
                <span className="mb-1 block text-sm font-medium text-muted">{t("tavern.trade.qty")}</span>
                <select className={field} value={form.ask_qty} onChange={(e) => setForm({ ...form, ask_qty: e.target.value })}>
                  {QTY.map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </label>
            </div>
          )}
          <Button type="submit" icon={Gift} loading={busy === "offer"} disabled={!form.to}>
            {t("tavern.trade.send")}
          </Button>
        </form>
      )}

      <section>
        <h2 className={sectionTitle}>{t("tavern.trade.incoming")}</h2>
        {data.incoming.length === 0 ? (
          <p className="text-sm text-muted">{t("tavern.trade.empty")}</p>
        ) : (
          <ul className="space-y-2">
            {data.incoming.map((trade) => (
              <li key={trade.id} className={`${panel} flex flex-wrap items-center justify-between gap-3`}>
                <p className="text-text">
                  <b>{trade.other.username}</b> {t("tavern.trade.offers")} {offerText(trade)}
                </p>
                <div className="flex gap-2">
                  <Button size="sm" icon={Check} loading={busy === `ok-${trade.id}`}
                    onClick={() => act(`ok-${trade.id}`, () => Social.tradeAction(trade.id, "accept"), t("tavern.trade.accepted"))}>
                    {t("tavern.trade.accept")}
                  </Button>
                  <Button size="sm" variant="outline" icon={X} loading={busy === `no-${trade.id}`}
                    onClick={() => act(`no-${trade.id}`, () => Social.tradeAction(trade.id, "decline"))}>
                    {t("tavern.trade.decline")}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {data.outgoing.length > 0 && (
        <section>
          <h2 className={sectionTitle}>{t("tavern.trade.outgoing")}</h2>
          <ul className="space-y-2">
            {data.outgoing.map((trade) => (
              <li key={trade.id} className={`${panel} flex flex-wrap items-center justify-between gap-3`}>
                <p className="text-text">
                  {t("tavern.trade.youOffer")} <b>{trade.other.username}</b>: {offerText(trade)}
                </p>
                <Button size="sm" variant="outline" loading={busy === `x-${trade.id}`}
                  onClick={() => act(`x-${trade.id}`, () => Social.tradeAction(trade.id, "cancel"))}>
                  {t("tavern.trade.cancel")}
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.history.length > 0 && (
        <section>
          <h2 className={sectionTitle}>{t("tavern.trade.history")}</h2>
          <ul className="space-y-1 text-sm text-muted">
            {data.history.map((trade) => (
              <li key={trade.id}>
                {trade.direction === "out" ? "→" : "←"} <b className="text-text">{trade.other.username}</b>: {offerText(trade)} —{" "}
                {t(`tavern.trade.statuses.${trade.status}`)}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

// ── гильдии ─────────────────────────────────────────────────────────────────

function GuildsTab({ t, errorText, myLevel, myId }) {
  const [data, setData] = useState(null);
  const [mine, setMine] = useState(null);
  const [busy, setBusy] = useState(null);
  const [form, setForm] = useState({ name: "", motto: "", emblem: "dragon" });

  const load = useCallback(async () => {
    try {
      const overview = await Social.guilds();
      setData(overview);
      setMine(overview.mine ? await Social.guild(overview.mine) : null);
    } catch (error) {
      toast.error(errorText(error));
    }
  }, [errorText]);
  useEffect(() => {
    load();
  }, [load]);

  const act = async (key, call, success) => {
    setBusy(key);
    try {
      await call();
      if (success) toast.success(success);
      await load();
    } catch (error) {
      toast.error(errorText(error));
    } finally {
      setBusy(null);
    }
  };

  if (!data) return <SkeletonScroll label={t("tavern.loading")} />;
  const minLevel = data.limits?.min_level ?? 2;

  return (
    <div className="space-y-6">
      {mine ? (
        <section className={`${panel} space-y-4`}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-widest text-primary">{t("tavern.guilds.mine")}</p>
              <h2 className="font-title text-2xl text-text">
                <span aria-hidden="true">{EMBLEMS[mine.emblem] || "🛡️"}</span> {mine.name}
              </h2>
              {mine.motto && <p className="mt-1 italic text-muted">«{mine.motto}»</p>}
            </div>
            <Button size="sm" variant="outline" icon={LogOut} loading={busy === "leave"}
              onClick={() => act("leave", () => Social.leaveGuild(), t("tavern.guilds.left"))}>
              {t("tavern.guilds.leave")}
            </Button>
          </div>
          <div>
            <h3 className="mb-2 text-sm font-semibold text-muted">
              {t("tavern.guilds.members")}: {mine.members}/{mine.max_members} · {mine.total_xp} XP
            </h3>
            <ul className="grid gap-2 sm:grid-cols-2">
              {mine.members_list.map((member) => (
                <li key={member.id} className="flex items-center justify-between gap-2 rounded-xl border border-border bg-surface px-3 py-2">
                  <span className="flex min-w-0 items-center gap-2">
                    {member.is_leader && <Crown size={16} className="shrink-0 text-[var(--wax)]" aria-label={t("tavern.guilds.leader")} />}
                    <span className="truncate text-text">{member.username}</span>
                    <span className="shrink-0 text-xs text-muted">{t("tavern.level")} {member.level} · {member.xp} XP</span>
                  </span>
                  {mine.is_leader && member.id !== myId && (
                    <Button size="sm" variant="ghost" loading={busy === `kick-${member.id}`}
                      onClick={() => act(`kick-${member.id}`, () => Social.kick(mine.id, member.id))}>
                      {t("tavern.guilds.kick")}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : (
        <form
          className={`${panel} space-y-4`}
          onSubmit={(event) => {
            event.preventDefault();
            act("found", () => Social.foundGuild(form), t("tavern.guilds.founded"));
          }}
        >
          <h2 className={sectionTitle}>{t("tavern.guilds.foundTitle")}</h2>
          {myLevel < minLevel && <p className="text-sm text-muted">{fill(t("tavern.guilds.minLevel"), { n: minLevel })}</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            <label>
              <span className="mb-1 block text-sm font-medium text-muted">{t("tavern.guilds.name")}</span>
              <input className={field} value={form.name} maxLength={40} required
                onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
            <label>
              <span className="mb-1 block text-sm font-medium text-muted">{t("tavern.guilds.motto")}</span>
              <input className={field} value={form.motto} maxLength={120}
                onChange={(e) => setForm({ ...form, motto: e.target.value })} />
            </label>
          </div>
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-muted">{t("tavern.guilds.emblem")}</legend>
            <div className="flex flex-wrap gap-2">
              {Object.entries(EMBLEMS).map(([id, icon]) => (
                <label key={id}
                  className={`flex min-h-[44px] cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-sm transition-colors ${
                    form.emblem === id ? "border-primary bg-primary/10 text-text" : "border-border text-muted hover:text-text"
                  }`}>
                  <input type="radio" name="emblem" value={id} className="sr-only" checked={form.emblem === id}
                    onChange={() => setForm({ ...form, emblem: id })} />
                  <span aria-hidden="true">{icon}</span> {t(`tavern.guilds.emblems.${id}`)}
                </label>
              ))}
            </div>
          </fieldset>
          <Button type="submit" icon={Shield} loading={busy === "found"} disabled={!form.name.trim() || myLevel < minLevel}>
            {t("tavern.guilds.found")}
          </Button>
        </form>
      )}

      <section>
        <h2 className={sectionTitle}>{t("tavern.guilds.ranking")}</h2>
        <p className="-mt-2 mb-3 text-sm text-muted">{t("tavern.guilds.rankingHint")}</p>
        {data.guilds.length === 0 ? (
          <EmptyScroll icon={Shield}>{t("tavern.guilds.empty")}</EmptyScroll>
        ) : (
          <ol className="space-y-2">
            {data.guilds.map((guild) => {
              const full = guild.members >= (data.limits?.members ?? 20);
              return (
                <li key={guild.id} className={`${panel} flex flex-wrap items-center gap-3 ${guild.id === data.mine ? "outline outline-2 outline-primary" : ""}`}>
                  <span className="w-10 shrink-0 font-title text-xl text-text">#{guild.place}</span>
                  <span className="text-2xl" aria-hidden="true">{EMBLEMS[guild.emblem] || "🛡️"}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-title text-lg text-text">{guild.name}</p>
                    <p className="text-xs text-muted">
                      {t("tavern.guilds.leader")}: {guild.leader || "—"} · {t("tavern.guilds.members")}: {guild.members}
                    </p>
                  </div>
                  <span className="font-title text-xl text-primary">{guild.total_xp} XP</span>
                  {!data.mine && (
                    <Button size="sm" variant="secondary" disabled={full} loading={busy === `join-${guild.id}`}
                      onClick={() => act(`join-${guild.id}`, () => Social.joinGuild(guild.id), t("tavern.guilds.joined"))}>
                      {full ? t("tavern.guilds.full") : t("tavern.guilds.join")}
                    </Button>
                  )}
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </div>
  );
}

// ── арена ───────────────────────────────────────────────────────────────────

function optionParts(option) {
  if (option && typeof option === "object") {
    const value = option.value ?? option.label ?? "";
    return { value: String(value), label: String(option.label ?? option.value ?? "") };
  }
  return { value: String(option), label: String(option) };
}

function DuelPlay({ t, duelId, errorText, onDone }) {
  const [state, setState] = useState(null);
  const [answers, setAnswers] = useState({});
  const [left, setLeft] = useState(null);
  const [sending, setSending] = useState(false);
  const sent = useRef(false);
  const answersRef = useRef(answers);
  answersRef.current = answers;

  const submit = useCallback(async () => {
    if (sent.current) return;
    sent.current = true;
    setSending(true);
    try {
      const result = await Social.submitDuel(duelId, answersRef.current);
      toast.success(`${t("tavern.arena.submitted")}: ${result.me.correct} ${t("tavern.arena.of")} ${result.questions}`);
    } catch (error) {
      toast.error(errorText(error));
    } finally {
      setSending(false);
      onDone();
    }
  }, [duelId, errorText, onDone, t]);

  useEffect(() => {
    let active = true;
    Social.startDuel(duelId)
      .then((data) => {
        if (!active) return;
        // часы сервера: дедлайн считается от его времени, а не от часов этого компьютера
        const skew = Date.parse(data.server_now) - Date.now();
        setState({ ...data, skew });
      })
      .catch((error) => {
        toast.error(errorText(error));
        onDone();
      });
    return () => {
      active = false;
    };
  }, [duelId, errorText, onDone]);

  useEffect(() => {
    if (!state) return undefined;
    const tick = () => {
      const seconds = Math.max(0, Math.round((Date.parse(state.deadline) - (Date.now() + state.skew)) / 1000));
      setLeft(seconds);
      if (seconds <= 0) submit();
    };
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [state, submit]);

  if (!state) return <SkeletonScroll label={t("tavern.loading")} rows={5} />;

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <div className={`${panel} sticky top-20 z-10 flex flex-wrap items-center justify-between gap-3`}>
        <p className="font-title text-lg text-text">
          {t("tavern.arena.vs")} {state.duel.opponent.username}
        </p>
        <p className={`flex items-center gap-2 font-title text-xl ${left != null && left <= 15 ? "text-error" : "text-primary"}`} aria-live="polite">
          <Timer size={18} aria-hidden="true" /> {t("tavern.arena.timeLeft")}: {left ?? state.seconds} {t("tavern.arena.sec")}
        </p>
      </div>
      {state.questions.map((question, index) => (
        <fieldset key={question.id} className={panel}>
          <legend className="sr-only">{t("tavern.arena.question")} {index + 1}</legend>
          <p className="mb-1 text-xs uppercase tracking-widest text-primary">
            {t("tavern.arena.question")} {index + 1}/{state.questions.length}
            {question.title ? ` · ${question.title}` : ""}
          </p>
          <div className="story-body mb-3 text-text" dangerouslySetInnerHTML={{ __html: sanitizeHtml(storyToHtml(question.body || "")) }} />
          <div className="grid gap-2 sm:grid-cols-2">
            {question.options.map((option, optionIndex) => {
              const { value, label } = optionParts(option);
              const chosen = answers[question.id] === value;
              return (
                <label key={`${question.id}-${optionIndex}`}
                  className={`flex min-h-[44px] cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 font-mono text-sm transition-colors ${
                    chosen ? "border-primary bg-primary/10 text-text" : "border-border text-text hover:bg-surface"
                  }`}>
                  <input type="radio" name={`q-${question.id}`} value={value} checked={chosen} className="accent-[var(--primary)]"
                    onChange={() => setAnswers((current) => ({ ...current, [question.id]: value }))} />
                  {label}
                </label>
              );
            })}
          </div>
        </fieldset>
      ))}
      <Button type="submit" icon={Swords} loading={sending}>
        {t("tavern.arena.submit")}
      </Button>
    </form>
  );
}

function ArenaTab({ t, friends, errorText, onChanged, prefill }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(null);
  const [opponent, setOpponent] = useState(prefill || "");
  const [playing, setPlaying] = useState(null);

  const load = useCallback(() => Social.duels().then(setData).catch((error) => toast.error(errorText(error))), [errorText]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (prefill) setOpponent(prefill);
  }, [prefill]);

  const finishPlay = useCallback(() => {
    setPlaying(null);
    load();
    onChanged();
  }, [load, onChanged]);

  const act = async (key, call, success) => {
    setBusy(key);
    try {
      await call();
      if (success) toast.success(success);
      await load();
      onChanged();
    } catch (error) {
      toast.error(errorText(error));
    } finally {
      setBusy(null);
    }
  };

  if (playing) return <DuelPlay t={t} duelId={playing} errorText={errorText} onDone={finishPlay} />;
  if (!data) return <SkeletonScroll label={t("tavern.loading")} />;
  const friendList = friends?.friends || [];
  const limits = data.limits || {};

  const sideText = (side, total) => {
    if (side.correct != null) return `${side.correct} ${t("tavern.arena.of")} ${total ?? limits.questions ?? 5}${side.late ? ` (${t("tavern.arena.late")})` : ""}`;
    return side.submitted ? "✓" : "…";
  };

  return (
    <div className="space-y-6">
      <section className={`${panel} space-y-3`}>
        <p className="text-sm text-muted">
          {fill(t("tavern.arena.rules"), { q: limits.questions ?? 5, s: limits.seconds ?? 120, d: limits.days ?? 3 })}
        </p>
        <p className="font-title text-lg text-text">
          {t("tavern.arena.record")}: {data.record.wins} · {data.record.draws} · {data.record.losses}
        </p>
        {friendList.length === 0 ? (
          <p className="text-sm text-muted">{t("tavern.arena.noFriends")}</p>
        ) : (
          <form
            className="flex flex-col gap-3 sm:flex-row sm:items-end"
            onSubmit={(event) => {
              event.preventDefault();
              act("challenge", () => Social.challenge(opponent), t("tavern.arena.challenged"));
            }}
          >
            <label className="flex-1">
              <span className="mb-1 block text-sm font-medium text-muted">{t("tavern.arena.choose")}</span>
              <select className={field} value={opponent} onChange={(e) => setOpponent(e.target.value)} required>
                <option value="">{t("tavern.arena.choose")}</option>
                {friendList.map((card) => <option key={card.id} value={card.username}>{card.username}</option>)}
              </select>
            </label>
            <Button type="submit" icon={Swords} loading={busy === "challenge"} disabled={!opponent}>
              {t("tavern.arena.challenge")}
            </Button>
          </form>
        )}
      </section>

      {data.duels.length === 0 ? (
        <EmptyScroll icon={Swords}>{t("tavern.arena.empty")}</EmptyScroll>
      ) : (
        <ul className="space-y-2">
          {data.duels.map((duel) => (
            <li key={duel.id} className={`${panel} flex flex-wrap items-center justify-between gap-3`}>
              <div className="min-w-0">
                <p className="font-title text-lg text-text">
                  {t("tavern.arena.vs")} {duel.opponent.username}
                  {duel.result && (
                    <span className={`ml-2 rounded-full px-2 py-0.5 text-xs font-bold ${
                      duel.result === "win" ? "bg-primary text-on-primary" : "border border-border text-muted"
                    }`}>
                      {t(`tavern.arena.result.${duel.result}`)}
                    </span>
                  )}
                </p>
                <p className="text-xs text-muted">
                  {t(`tavern.arena.statuses.${duel.status}`)} · {t("tavern.arena.you")}: {sideText(duel.me, duel.questions)} · {t("tavern.arena.them")}: {sideText(duel.them, duel.questions)}
                  {duel.status === "active" && ` · ${duel.can_start ? t("tavern.arena.waitingYou") : t("tavern.arena.waitingThem")}`}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {duel.can_start && (
                  <Button size="sm" icon={Swords} onClick={() => setPlaying(duel.id)}>{t("tavern.arena.play")}</Button>
                )}
                {duel.can_decline && (
                  <Button size="sm" variant="outline" loading={busy === `d-${duel.id}`}
                    onClick={() => act(`d-${duel.id}`, () => Social.duelAction(duel.id, "decline"))}>
                    {t("tavern.arena.decline")}
                  </Button>
                )}
                {duel.can_cancel && (
                  <Button size="sm" variant="ghost" loading={busy === `c-${duel.id}`}
                    onClick={() => act(`c-${duel.id}`, () => Social.duelAction(duel.id, "cancel"))}>
                    {t("tavern.arena.cancel")}
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── страница ────────────────────────────────────────────────────────────────

export default function Tavern() {
  const { t } = useI18n();
  const errorText = useErrorText(t);
  const [me, setMe] = useState(undefined); // undefined: ещё грузим, null: не удалось
  const [tab, setTab] = useState("friends");
  const [status, setStatus] = useState({});
  const [friends, setFriends] = useState(null);
  const [prefill, setPrefill] = useState({});

  useEffect(() => {
    Profile.me().then(setMe).catch(() => setMe(null));
  }, []);
  const player = !!me && !canTeach(me) && me.social_enabled !== false;

  const refreshStatus = useCallback(() => {
    Social.status().then(setStatus).catch(() => {});
  }, []);
  useEffect(() => {
    if (!player) return;
    refreshStatus();
    Social.friends().then(setFriends).catch((error) => toast.error(errorText(error)));
  }, [player, refreshStatus, errorText]);

  const goTo = (next, username) => {
    setPrefill((current) => ({ ...current, [next]: username }));
    setTab(next);
  };

  const notice = useMemo(() => {
    if (me === null) return t("tavern.errors.generic");
    if (me && me.social_enabled === false) return t("tavern.off");
    if (me && canTeach(me)) return t("tavern.teacherOnly");
    return null;
  }, [me, t]);

  return (
    <Layout>
      <div className="mx-auto max-w-5xl px-4 pb-12 pt-24">
        <header className="mb-8 text-center">
          <div className="mb-5 inline-flex h-16 w-16 items-center justify-center rounded-3xl border border-primary/20 bg-primary/10 text-primary">
            <Users size={32} aria-hidden="true" />
          </div>
          <p className="mb-2 text-xs uppercase tracking-widest text-primary">{t("tavern.eyebrow")}</p>
          <h1 className="mb-3 font-title text-4xl text-text md:text-5xl">{t("tavern.title")}</h1>
          <p className="mx-auto max-w-2xl text-muted">{t("tavern.subtitle")}</p>
        </header>

        {me === undefined ? (
          <SkeletonScroll label={t("tavern.loading")} />
        ) : notice ? (
          <EmptyScroll icon={Users}>{notice}</EmptyScroll>
        ) : (
          <>
            <div role="tablist" aria-label={t("tavern.tabs.label")} className="mb-6 flex flex-wrap gap-2 rounded-2xl border border-border bg-panel p-2">
              {TABS.map(({ id, icon: Icon, badge }) => {
                const count = badge ? status[badge] : 0;
                return (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    id={`tab-${id}`}
                    aria-selected={tab === id}
                    aria-controls={`panel-${id}`}
                    onClick={() => setTab(id)}
                    className={`flex min-h-[44px] items-center gap-2 rounded-xl border px-4 text-sm font-semibold transition-colors ${
                      tab === id ? "border-primary bg-primary text-on-primary" : "border-border text-muted hover:bg-surface/50 hover:text-text"
                    }`}
                  >
                    <Icon size={16} aria-hidden="true" />
                    {t(`tavern.tabs.${id}`)}
                    {count > 0 && (
                      <span className="rounded-full bg-[var(--wax)] px-2 py-0.5 text-xs font-bold text-white">{count}</span>
                    )}
                  </button>
                );
              })}
            </div>
            <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
              {tab === "friends" && (
                <FriendsTab t={t} data={friends} setData={setFriends} errorText={errorText} onChanged={refreshStatus} goTo={goTo} />
              )}
              {tab === "trade" && (
                <TradeTab t={t} friends={friends} errorText={errorText} onChanged={refreshStatus} prefill={prefill.trade} />
              )}
              {tab === "guilds" && <GuildsTab t={t} errorText={errorText} myLevel={me.level ?? 1} myId={me.id} />}
              {tab === "arena" && (
                <ArenaTab t={t} friends={friends} errorText={errorText} onChanged={refreshStatus} prefill={prefill.arena} />
              )}
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
