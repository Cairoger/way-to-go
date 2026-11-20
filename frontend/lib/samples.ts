import type { Trip } from './trips';

type Stop = [string, string, string];
type Sample = { trip: Trip; travellers: string[]; days: { title: string; stops: Stop[] }[] };
function trip(
  id: string,
  title: string,
  destinations: string[],
  cover: string,
  start: string,
  end: string,
  count: number,
  days: number,
  status: Trip['status'],
  description: string,
): Trip {
  return {
    id,
    title,
    destinations,
    cover,
    start_date: start,
    end_date: end,
    description,
    status,
    currency: id === 'kyoto' ? 'JPY' : id === 'dolomites' ? 'EUR' : 'TWD',
    archived: false,
    deleted_at: null,
    version: 1,
    owner_id: 'sample',
    member_count: count,
    day_count: days,
    place_count: days * 2,
    created_at: start,
  };
}
export const samples: Sample[] = [
  {
    trip: trip(
      'kyoto',
      '京都秋日散策',
      ['日本', '京都'],
      'kyoto',
      '2026-11-25',
      '2026-11-28',
      3,
      4,
      'planning',
      '沿著鴨川與古寺的石板路，在京都慢慢走四天。',
    ),
    travellers: ['葵', '哲', '晴'],
    days: [
      {
        title: '東山的午後',
        stops: [
          ['12:00', '京都車站', '在中央口集合，先寄放行李。'],
          ['15:00', '八坂之塔', '從二年坂散步到法觀寺。'],
        ],
      },
      {
        title: '嵐山散步',
        stops: [
          ['09:00', '嵐山竹林', '趁早出發，走一段安靜的小徑。'],
          ['12:00', '渡月橋', '在桂川河畔享用午餐。'],
        ],
      },
      {
        title: '伏見與鴨川',
        stops: [
          ['09:30', '伏見稻荷大社', '沿千本鳥居拾級而上。'],
          ['16:00', '鴨川三角洲', '找一張河畔長椅看天色變化。'],
        ],
      },
      {
        title: '市場與歸途',
        stops: [
          ['10:00', '錦市場', '挑選漬物與茶葉。'],
          ['14:00', '京都車站', '取行李，搭車返程。'],
        ],
      },
    ],
  },
  {
    trip: trip(
      'dolomites',
      '多洛米蒂山間漫遊',
      ['義大利', '多洛米蒂'],
      'alps',
      '2027-06-12',
      '2027-06-16',
      4,
      5,
      'confirmed',
      '沿著義大利北部的山間步道與湖泊，走一段五日健行。',
    ),
    travellers: ['安', '凱', '瑜', '恩'],
    days: [
      {
        title: '抵達山谷',
        stops: [
          ['11:00', '波札諾', '集合後採買登山補給。'],
          ['15:00', '奧蒂塞伊', '入住山間小鎮，傍晚散步。'],
        ],
      },
      {
        title: '休斯高原',
        stops: [
          ['08:30', '休斯高原', '搭纜車前往草甸。'],
          ['13:00', '薩索隆戈觀景點', '山屋午餐後眺望山脊。'],
        ],
      },
      {
        title: '山脊健行',
        stops: [
          ['09:00', '塞切達山', '沿稜線步道欣賞群峰。'],
          ['14:00', '菲內斯山谷', '探訪山谷裡的小教堂。'],
        ],
      },
      {
        title: '湖畔慢行',
        stops: [
          ['08:00', '布萊埃斯湖', '繞湖步行，記錄晨光。'],
          ['14:00', '多比亞科', '回小鎮享用下午茶。'],
        ],
      },
      {
        title: '返回城市',
        stops: [
          ['09:00', '卡雷扎湖', '沿森林步道散步。'],
          ['15:00', '波札諾車站', '集合搭車返程。'],
        ],
      },
    ],
  },
  {
    trip: trip(
      'tainan',
      '台南巷弄小旅行',
      ['台灣', '台南'],
      'tainan',
      '2026-10-16',
      '2026-10-18',
      2,
      3,
      'completed',
      '從府城老屋、街邊小吃，走到安平的海風裡。',
    ),
    travellers: ['宇', '庭'],
    days: [
      {
        title: '走進府城',
        stops: [
          ['10:00', '台南車站', '集合後步行前往中西區。'],
          ['15:00', '神農街', '探訪巷弄工藝店。'],
        ],
      },
      {
        title: '安平日落',
        stops: [
          ['10:00', '安平古堡', '散步認識安平的歷史。'],
          ['17:00', '漁光島', '到海灘欣賞日落。'],
        ],
      },
      {
        title: '市場早午餐',
        stops: [
          ['09:00', '水仙宮市場', '尋找當地早點。'],
          ['13:00', '林百貨', '挑伴手禮，準備返程。'],
        ],
      },
    ],
  },
];
