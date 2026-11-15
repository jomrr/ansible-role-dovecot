-- The mailbox columns consumed by Dovecot exist in the PostfixAdmin schema.
CREATE TABLE IF NOT EXISTS mailbox (
    username VARCHAR(255) PRIMARY KEY,
    password VARCHAR(255) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);
DELETE FROM mailbox;
INSERT INTO mailbox (username, password, active) VALUES
('local@mail.test', '{SHA512-CRYPT}$6$dovecotfixture$nJZZj3C.o5vFWgDGA0iKfaH1Nkh.X7YmBW/XxbdKjqMJFQlqoK68wFo4OjGZu1AE8epNkeV4h/27kwps1UGE..', TRUE),
('adsql@mail.test', '*', TRUE),
('inactive@mail.test', '{SHA512-CRYPT}$6$dovecotfixture$nJZZj3C.o5vFWgDGA0iKfaH1Nkh.X7YmBW/XxbdKjqMJFQlqoK68wFo4OjGZu1AE8epNkeV4h/27kwps1UGE..', FALSE);
