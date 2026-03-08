export type GreetingKind = 'holiday' | 'weekday' | 'weekend'

type HolidayCalendar = {
  offDays: ReadonlySet<string>
  workdays: ReadonlySet<string>
}

type GreetingDescriptor = {
  kind: GreetingKind
  title: string
}

const SHANGHAI_OFFSET_MS = 8 * 60 * 60 * 1000
const greetingTitles: Record<GreetingKind, string> = {
  holiday: '节假日愉快，工作的事交给我',
  weekday: '工作日愉快，工作的事交给我',
  weekend: '周末愉快，工作的事交给我',
}

function createHolidayCalendar(offDays: string[], workdays: string[]): HolidayCalendar {
  return {
    offDays: new Set(offDays),
    workdays: new Set(workdays),
  }
}

const holidayCalendars: Record<number, HolidayCalendar> = {
  2026: createHolidayCalendar(
    [
      '2026-01-01',
      '2026-01-02',
      '2026-01-03',
      '2026-02-15',
      '2026-02-16',
      '2026-02-17',
      '2026-02-18',
      '2026-02-19',
      '2026-02-20',
      '2026-02-21',
      '2026-02-22',
      '2026-02-23',
      '2026-04-04',
      '2026-04-05',
      '2026-04-06',
      '2026-05-01',
      '2026-05-02',
      '2026-05-03',
      '2026-05-04',
      '2026-05-05',
      '2026-06-19',
      '2026-06-20',
      '2026-06-21',
      '2026-09-25',
      '2026-09-26',
      '2026-09-27',
      '2026-10-01',
      '2026-10-02',
      '2026-10-03',
      '2026-10-04',
      '2026-10-05',
      '2026-10-06',
      '2026-10-07',
    ],
    [
      '2026-01-04',
      '2026-02-14',
      '2026-02-28',
      '2026-05-09',
      '2026-09-20',
      '2026-10-10',
    ],
  ),
  2027: createHolidayCalendar([], []),
}

function pad(value: number) {
  return String(value).padStart(2, '0')
}

function getShanghaiDateSnapshot(date: Date) {
  const shanghaiDate = new Date(date.getTime() + SHANGHAI_OFFSET_MS)

  return {
    year: shanghaiDate.getUTCFullYear(),
    month: shanghaiDate.getUTCMonth() + 1,
    day: shanghaiDate.getUTCDate(),
    weekday: shanghaiDate.getUTCDay(),
  }
}

function getShanghaiDateKey(date: Date) {
  const { year, month, day } = getShanghaiDateSnapshot(date)
  return `${year}-${pad(month)}-${pad(day)}`
}

export function resolveGreeting(date = new Date()): GreetingDescriptor {
  const dateKey = getShanghaiDateKey(date)
  const { year, weekday } = getShanghaiDateSnapshot(date)
  const calendar = holidayCalendars[year]
  const hasPublishedHolidayRules =
    calendar !== undefined && (calendar.offDays.size > 0 || calendar.workdays.size > 0)

  if (hasPublishedHolidayRules) {
    if (calendar.offDays.has(dateKey)) {
      return {
        kind: 'holiday',
        title: greetingTitles.holiday,
      }
    }

    if (calendar.workdays.has(dateKey)) {
      return {
        kind: 'weekday',
        title: greetingTitles.weekday,
      }
    }
  }

  const kind: GreetingKind = weekday === 0 || weekday === 6 ? 'weekend' : 'weekday'

  return {
    kind,
    title: greetingTitles[kind],
  }
}

export function getMillisecondsUntilNextShanghaiMidnight(date = new Date()) {
  const shanghaiDate = new Date(date.getTime() + SHANGHAI_OFFSET_MS)
  const nextShanghaiMidnight =
    Date.UTC(
      shanghaiDate.getUTCFullYear(),
      shanghaiDate.getUTCMonth(),
      shanghaiDate.getUTCDate() + 1,
    ) - SHANGHAI_OFFSET_MS

  return Math.max(nextShanghaiMidnight - date.getTime(), 1)
}
