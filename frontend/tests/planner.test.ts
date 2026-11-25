import { expect, it } from 'vitest';
import { parseGooglePlaceLink, type Place, type TripDay } from '../components/plannerTypes';
import { printableDays } from '../components/PlannerTools';

it('parses explicit pin coordinates and leaves unknown short links for manual entry', () => {
  expect(
    parseGooglePlaceLink(
      'https://www.google.com/maps/place/Taipei+101/@2,3,14z/data=!3d25.03!4d121.56',
    ),
  ).toEqual({ name: 'Taipei 101', latitude: 25.03, longitude: 121.56 });
  expect(parseGooglePlaceLink('https://maps.google.com/?q=25,121')).toEqual({
    name: '',
    latitude: 25,
    longitude: 121,
  });
  expect(parseGooglePlaceLink('https://maps.app.goo.gl/xyz')).toBeNull();
  expect(parseGooglePlaceLink('https://google.com.evil.invalid/maps/place/Unexpected')).toBeNull();
  expect(parseGooglePlaceLink('https://www.google.com/maps/place/Taipei/@2,3,14z')).toEqual({
    name: 'Taipei',
    latitude: null,
    longitude: null,
  });
});

it('prints only allowlisted itinerary fields even in detailed mode', () => {
  const days = [
    {
      day_number: 1,
      title: '市區',
      timezone: 'Asia/Taipei',
      items: [
        {
          title: '散步',
          start_time: '09:00',
          item_type: 'place',
          place_id: 'p',
          notes: '私人代號',
          reservation: '123ABC',
        },
      ],
    },
  ] as unknown as TripDay[];
  const places = [{ id: 'p', address: '中山路', notes: '私人文件', cost: 12345 }] as Place[];
  const output = JSON.stringify(printableDays(days, places, true));
  expect(output).toContain('中山路');
  for (const value of ['私人代號', '123ABC', '私人文件', '12345'])
    expect(output).not.toContain(value);
  expect(JSON.stringify(printableDays(days, places, false))).not.toContain('中山路');
});
