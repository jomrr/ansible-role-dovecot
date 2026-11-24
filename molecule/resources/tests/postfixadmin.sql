-- The fixture extends the PostfixAdmin columns with POSIX storage identities.
CREATE TABLE IF NOT EXISTS mailbox (
    username VARCHAR(255) PRIMARY KEY,
    uid INTEGER NOT NULL UNIQUE,
    gid INTEGER NOT NULL,
    password VARCHAR(255) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);
DELETE FROM mailbox;
INSERT INTO mailbox (username, uid, gid, password, active) VALUES
('local@mail.test', 70201, 70100, '{SHA512-CRYPT}$6$dovecotfixture$nJZZj3C.o5vFWgDGA0iKfaH1Nkh.X7YmBW/XxbdKjqMJFQlqoK68wFo4OjGZu1AE8epNkeV4h/27kwps1UGE..', TRUE),
('baduid@mail.test', 69999, 70100, '*', TRUE),
('badgid@mail.test', 70204, 69999, '*', TRUE),
('drift@mail.test', 70205, 70100, '*', TRUE),
('adsql@mail.test', 70102, 70100, '*', TRUE),
('inactive@mail.test', 70203, 70100, '{SHA512-CRYPT}$6$dovecotfixture$nJZZj3C.o5vFWgDGA0iKfaH1Nkh.X7YmBW/XxbdKjqMJFQlqoK68wFo4OjGZu1AE8epNkeV4h/27kwps1UGE..', FALSE);
