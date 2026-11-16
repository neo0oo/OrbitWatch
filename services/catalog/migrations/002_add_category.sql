ALTER TABLE satellites ADD category NVARCHAR(50) NOT NULL
    CONSTRAINT df_satellites_category DEFAULT 'other';

EXEC('UPDATE satellites SET category = ''space station'' WHERE norad_id = 25544');
EXEC('UPDATE satellites SET category = ''telescope'' WHERE norad_id = 20580');
